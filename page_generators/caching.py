import functools

def memoize_by_first_arg(func):
    """
    A simple memoization decorator that caches results based on the first argument.
    This is suitable for functions where the first argument is the primary identifier
    for the data being fetched, like a tournament ID or list of IDs.
    """
    cache = {}
    @functools.wraps(func)
    def wrapper(first_arg, *args, **kwargs):
        # Create a cache key from the first argument.
        # If it's a list, convert it to a sorted tuple to make it hashable.
        if isinstance(first_arg, list):
            key = tuple(sorted(first_arg))
        else:
            key = first_arg

        if key not in cache:
            # Call the original function with all its arguments
            cache[key] = func(first_arg, *args, **kwargs)
        
        return cache[key]
    return wrapper
