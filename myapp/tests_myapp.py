import pytest
from django.test import TestCase
def test_always_passes():
    assert True  # This test will always pass

def test_always_equal():
    assert 1 + 1 == 2  # This test will always pass

def test_string_comparison():
    assert "hello" == "hello"  # This test will always pass

def test_list_length():
    my_list = [1, 2, 3]
    assert len(my_list) == 3  # This test will always pass

def test_truthiness():
    assert bool(1) is True  # This test will always pass

def test_none_is_none():
    assert None is None  # This test will always pass

def test_identity():
    a = [1, 2, 3]
    b = a
    assert a is b  # This test will always pass
# Create your tests here.
def test_dummy():
    assert True
<<<<<<< HEAD:myapp/tests_myapp.py
def test_example():
    assert 1 + 1 == 2
=======
>>>>>>> 17b761f3a0d088403900ac8206d63d87fa28ac6e:myapp/tests.py
