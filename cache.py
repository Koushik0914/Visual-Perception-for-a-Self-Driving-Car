import numpy as np

class Cache:
    def __init__(self, max_size=10):
        self.cache = []
        self.max_size = max_size

    def add(self, element):
        self.cache.append(element)
        if len(self.cache) > self.max_size:
            self.cache.pop(0)  # Remove the first element to maintain the max_size limit

    def mean(self, i):
        column = [element[i] for element in self.cache]
        return np.mean(column)  # Numpy handles the mean directly from the list

    def empty(self):
        return len(self.cache) == 0

    def get_size(self):
        return len(self.cache)

    def get_last(self):
        if self.empty():
            raise ValueError("Cache is empty")
        return self.cache[-1]  # Access the last element safely

    def get_all(self):
        return self.cache
    
    def get_all_index(self, i):
        return [row[i] for row in self.cache]

    def print_cache(self):
        for e in self.cache:
            print(e)

if __name__ == '__main__':
    print('=== Test Cache ===')
    cache = Cache(max_size=5)
    cache.add([5,4])
    print(cache.get_size())
    cache.print_cache()

    cache.add([8,1])
    cache.add([3,2])
    cache.add([4,5])
    cache.add([6,2])
    print(cache.get_size())
    cache.print_cache()

    cache.add([1,4])
    print(cache.get_size())
    cache.print_cache()

    # Example of using the mean function
    print("Mean of column 0:", cache.mean(0))
    print("Mean of column 1:", cache.mean(1))
