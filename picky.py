#!/usr/bin/python
"""
This module contains 'Picky', a tool intended to cherry-pick data from
django querysets (or any iterator) while leaving the non-picked model
instances availible for later iteration.

An instance of cherry-picking from the query set is initiated with
the Picky.filter(f) function that returns a new Picky instance. Iterating
over the new Picky instance will yield only the matched elements specified by
the filter parameter from the parents Picky instance. 

Example usage:

>>> import itertools
>>> p = Picky(IteratorSource(itertools.count()))

Iterating over p is now roughly equivilent as iterating
over itertools.count()

>>> p.next()
0
>>> p.next()
1
>>> p.last()
1
>>> p.peek()
2
>>> p.next()
2

The elements that have been consumed from the Picky are kept track
if with the consumed attribute.

>>> p.consumed
[0, 1, 2]

Items can also be consumed fromt the iterator with the slice syntax,
it will consume the items and return them to you in a list. If you want
a Picky instance for the sliced elements, use the slice method.

>>> p[:3]
[3, 4, 5]
>>> p.slice(5, 6).peek()
11
>>> p.slice(5, 6).next()
11
>>> list(p.slice(stop=2))
[6, 7]

Contruct filters for even and odd numbers

>>> even = p.filter(lambda n: n%2==0)
>>> odd = p.filter(lambda n: n%2==1)
>>> even.next() # 0-7 and 11 already consumed, expecting 8 and 10
8
>>> even.next()
10
>>> odd.next()
9
>>> p[0]
12

Further tests

>>> p.peek() == p.next() # 13
True
>>> p.next()
14
>>> p[:3]
[15, 16, 17]
>>> p.next()
18
>>> list(even[:2])
[20, 22]

Let's filter out the primes from the naterual numbers >= 2
>>> numbers = Picky(IteratorSource(itertools.count(2)))
>>> primes = numbers.filter(lambda n: all([n%p!=0 for p in primes.consumed]))
>>> primes[:12]
[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37]

An old-and-fixed stack limitation:
>>> over9000 = numbers.filter(lambda n: n>9000)
>>> over9000.next()
9001
"""
import operator
try:
    from django.db.models.query import QuerySet
except: # no django environment
    class QuerySet: pass


## SUPPORT CLASSES
class Source(object):
    """Instance that provides the next element in the chain callback"""
    @property
    def next(self):
        """Returns a new ElementWrapper with the obj property set"""
        raise StopIteration


class ElementWrapper(object):
    """ElementWrappers are combined in to a one-way linked lists"""
    def __init__(self, source, obj=None):
        self.source = source
        self.obj = obj
        self.consumed = False

    @property
    def next(self):
        if not hasattr(self, '_next'):
            self._next = self.source.next()
        return self._next


## SOURCES
class ListSource(Source):
    def __init__(self, lst):
        self.lst = lst

    def next(self):
        e = ElementWrapper(self)
        try:
            e.obj = self.lst.pop(0)
        except IndexError:
            raise StopIteration
        return e


class IteratorSource(Source):
    def __init__(self, gen):
        self.gen = gen

    def next(self):
        return ElementWrapper(self, self.gen.next())


class MergeSource(Source):
    def __init__(self, a, b, f=operator.__le__):
        self.a, self.b = a, b
        self.f = f

    def next(self):
        def get_obj():
            try:
                pa = self.a.peek()
            except StopIteration:
                return self.b.next()
            try:
                pb = self.b.peek()
            except StopIteration:
                return self.a.next()
        
            if self.f(pa, pb):
                return self.a.next()
            else:
                return self.b.next()
        return ElementWrapper(self, get_obj())


class QuerySetSource(Source):
    def __init__(self, qs, chunksize=25, max_iterations=8, initial_excludes=None):
        self.qs = qs
        self.chunksize = chunksize
        self.max_iterations = max_iterations
        self.index = 0
        self.res = None
        self.initial_excludes = initial_excludes

    def feed(self):
        if self.index == self.max_iterations:
            raise StopIteration, "Runaway picky!"
        if self.index == 0 and self.initial_excludes:
            self.qs = self.qs.exclude(id__in=[x.id for x in self.initial_excludes])
        self.res = list(self.qs[self.index*self.chunksize:(self.index+1)*self.chunksize])
        if not self.res:
            raise StopIteration
        self.index += 1

    def next(self):
        if not self.res:
            self.feed()
        return ElementWrapper(self, self.res.pop(0))


class Picky(object):
    def __init__(self, source, e=None, filters={}, **skw):
        """
        `source` should be in instance of a subclass of
        Source, but other common sources are accepted.
        
        The initializer will set our 'e' attribute, our
        point of no-return on the element chain, as well as
        our source instance.
        """
        if isinstance(source, list):
            source = ListSource(source, **skw)
        elif isinstance(source, QuerySet):
            source = QuerySetSource(source, **skw)
#        elif hasattr(source, 'next'):
#            source = IteratorSource(source, **skw)
        elif source is None:
            raise ValueError, "Picky wants an iterable"
        
        if e is None:
            if isinstance(source, Source):
                # initial element
                #e = source.next() deferring execution
                pass
            elif isinstance(source, Picky):
                # inherit parent picky's position
                e = source.e

        self.source = source
        self.e = e

        self.filters = filters
        self.consumed = []
        self.consumed_by_self = []

    def __iter__(self):
        return self
    
    def __getitem__(self, index):
        """
        Wrapper around slice, but will return a list
        if selected items and mark them as consumed.
        """
        if isinstance(index, int):
            # p[n] syntax, return one value
            return self.slice(index, index+1).next()
        else:
            # p[a:b(:c)?] syntax
            args = {}
            if index.start and index.start > 0:
                args['start'] = index.start
            if index.stop:
                args['stop'] = index.stop
            if index.step and index.step > 1:
                args['step'] = index.step
            return list(self.slice(**args))

    def __len__(self):
        # XXX: Remove me
        if 'n' in self.filters:
            return self.filters['n'] - len(self.consumed_by_self)

    def __run(self, e=None):
        while 1:
            # run our own element if none specified
            if e is None:
                if self.e is None and isinstance(self.source, Source):
                    self.e = self.source.next()
                e = self.e
            if isinstance(self.source, Picky):
                e = self.source.__run(e)
            
            # max out at self.filters['n'] items
            if 'n' in self.filters:
                if len(self.consumed_by_self) >= self.filters['n']:
                    raise StopIteration

            # jump over consumed elements
            while e.consumed:
                e = e.next

            # function filter
            if 'f' in self.filters and not self.filters['f'](e.obj):
                e = e.next
                continue
            # predicament filter
            if 'p' in self.filters:
                if self.filters['p'] is False:
                    raise StopIteration
                elif not self.filters['p'](e.obj):
                    self.filters['p'] = False
                    raise StopIteration

            if 'stepping' in self.filters:
                if not '_step' in self.filters:
                    self.filters['_step'] = 0
                else:
                    self.filters['_step'] += 1
                    self.filters['_step'] %= self.filters['stepping']
                if not self.filters['_step'] == 0:
                    e = e.next
                    continue
            break
        return e

    def next(self):
        """
        Returns the next element and consumes it.
        """
        e = self.__run()
        e.consumed = True
        self.e = e
        # keep track of consumed object
        self.consumed_by_self.append(e.obj)
        self.consumed.append(e.obj)
        # because we did not call next() on the parent picky the item
        # will not be added to parent's picky. Manually go up the tree
        # adding to every consumed list.
        s = self.source
        while isinstance(s, Picky):
            s.consumed.append(e.obj)
            s = s.source
        return e.obj

    def peek(self):
        """
        Returns the next element without consuming it.
        """
        e = self.__run()
        return e.obj

    def slice(self, start=None, stop=None, step=None):
        """
        Returns a picky of the sliced elements.

        >>> p = Picky(range(10))
        >>> p[:3:2]
        [0, 2, 4]
        >>> p[1]
        3
        >>> p[:2:5]
        [1, 9]
        >>> p[2:4]
        [7, 8]
        """
        # TODO: Proper usage error exception
        assert any([start, stop, step]), "Usage error"
        
        filters = {}
        e = self.e
        if not start is None:
            # we'll fast-forward the element `start` items ahead
            e = self.__run()
            for n in range(start):
                e = e.next
        if not stop is None:
            filters['n'] = stop
        if not step is None:
            filters['stepping'] = step
        return Picky(self, e, filters)

    def filter(self, f):
        return Picky(self, filters={'f': f})

    def all(self):
        # XXX: This probably doesn't work as intended
        return Picky(self, filters={})

    def merge(self, p, f=operator.__le__):
        """
        Join two Pickys.

        p is the Picky to merge with.
        f is a function that compares the next items of both pickys
          and decides which one should go next by returning True
          to pick from this picky or False by picking from p.

        >>> a = Picky(ListSource([1, 3, 5, 7, 9]))
        >>> b = Picky(ListSource([2, 4, 6, 8, 10]))
        >>> c = a.merge(b, lambda x, y: x < y)
        >>> list(c)
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        """
        return Picky(MergeSource(self, p, f))

    def __add__(self, other):
        """Alias for merge"""
        return self.merge(other, lambda a, b: True)

    def has_more(self):
        """
        Returns the boolean value of whether there is another element
        availible for consumption in this picky.

        >>> a = Picky(range(3))
        >>> (a.next(), a.next())
        (0, 1)
        >>> a.has_more()
        True
        >>> a.next()
        2
        >>> a.has_more()
        False
        """
        try:
            self.peek()
            return True
        except StopIteration:
            return False

    def intercepted(self, picky, key=None):
        """
        Intercept elements in self from `picky`s *consumed* elements.

        >>> a = Picky([1, 3, 7, 0])
        >>> a[:2]
        [1, 3]
        >>> b = Picky(range(10)).intercepted(a)
        >>> list(b)
        [0, 2, 4, 5, 6, 7, 8, 9]

        >>> a = Picky([9, 8, 7, 6])
        >>> b = Picky([3, 4, 5, 6]).intercepted(a)
        >>> b[3]
        6
        >>> list(a)
        [9, 8, 7, 6]
        """
        if isinstance(self.source, QuerySetSource):
            self.source.initial_excludes = picky.consumed
        if key:
            r = self.filter(lambda n: not key(n) in (key(x) for x in picky.consumed))
        else:
            r = self.filter(lambda n: not n in picky.consumed)
        return r

    def __sub__(self, other):
        """Alias for intercepted"""
        return self.intercepted(other)

    def step(self, n):
        """
        Iterate over every `steps` elements.

        >>> p = Picky(range(10))
        >>> everyother = p.step(2)
        >>> list(everyother)
        [0, 2, 4, 6, 8]
        >>> list(p)
        [1, 3, 5, 7, 9]
        """
        return self.slice(step=n)

    def __mod__(self, i):
        """Alias for step"""
        return self.step(i)

    def last(self):
        """
        Returns the same element as the last next() call to *this* picky.
        If you want the latest yielded element from this picky and filters
        made from it, use self.consumed[-1]
        XXX: Needs tests
        """
        return self.e.obj

    def takewhile(self, predicament):
        """
        Create a new iterator that yields elements as long as
        predicament is True, styling itertools.takewhile.

        This method is similar to filter, but whereas filter will
        not iterate over unmatched elements, takewhile only matches
        elements up to and not including the first failed predicament.

        >>> p = Picky([4, 1, 6, 3, 8, 0, 11, 9, 3, 13])
        >>> list(p.takewhile(lambda obj: obj < 10))
        [4, 1, 6, 3, 8, 0]

        XXX: Needs better tests
        """
        return Picky(self, filters={'p': predicament})


if __name__ == "__main__":
    import doctest
    doctest.testmod()
