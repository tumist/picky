Picky
=====

Picky is an iterator (http://docs.python.org/2.7/glossary.html#term-iterator)
of ordered, bound or un-bound containers and features methods to iterate
a subset of a container using various filtering methods inspired by the
`itertools` package. Such methods yield their own nested Picky iterators.

A yielded element is considered *consumed* and will not be yielded by any
children Pickys nor parents. This means that iterating over set B ⊂ A
will inhibit yielded elements from iteration of A. Below is a demonstration:

```python

>>> numbers = Picky([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
>>> even_numbers = numbers.filter(lambda num: num % 2 == 0)
>>> list(even_numbers)
[0, 2, 4, 6, 8]
>>> list(numbers)
[1, 3, 5, 7, 9]
```
