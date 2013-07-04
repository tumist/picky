Picky
=====

Picky is an iterator (http://docs.python.org/2.7/glossary.html#term-iterator)
of ordered, finite (lists, QuerySets) or infinite (generators containers)
collections and features methods to iterate over a subset of the collections
using various filtering functions inspired by the `itertools` package.

A yielded element is considered *consumed* and will not be yielded by any Picky
iterators derived filtering methods. In other words iterating over set B ⊂ A
will inhibit previously yielded elements from iteration of A.
Below is a demonstration:

```python

>>> numbers = Picky([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
>>> even_numbers = numbers.filter(lambda num: num % 2 == 0)
>>> list(even_numbers)
[0, 2, 4, 6, 8]
>>> list(numbers)
[1, 3, 5, 7, 9]

```

One way to enumerate prime numbers is to mark all multiples of the first prime
(2) as non-primes and then repeating for the next successive number that isn't
marked non-prime (3) until desired number of primes have been computed.

```python

>>> num = Picky(count(2))
>>> for i in range(16):
...     prime = num.next()
...     print prime
...     def factory(p):
...         def filter_func(n):
...             return n%p != 0
...         return filter_func
...    num = num.filter(factory(prime))

```
