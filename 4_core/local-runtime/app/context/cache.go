// app/context/cache.go - Context Cache with LRU Eviction
// Thread-safe LRU cache for assembled contexts
package context

import (
	"container/list"
	"sync"
)

type cacheEntry struct {
	key   string
	value *cachedContext
}

type cachedContext struct {
	text             string
	totalTokens      int
	usedItems        int
	compressionRatio float64
}

// Cache is a thread-safe LRU cache for assembled contexts
type Cache struct {
	mu    sync.RWMutex
	items map[string]*list.Element
	list  *list.List
	cap   int
}

// NewCache creates a new cache with the specified capacity
func NewCache(capacity int) *Cache {
	return &Cache{
		items: make(map[string]*list.Element),
		list:  list.New(),
		cap:   capacity,
	}
}

// Get retrieves a cached context by key
func (c *Cache) Get(key string) *cachedContext {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		c.list.MoveToFront(elem)
		return elem.Value.(*cacheEntry).value
	}
	return nil
}

// Set stores a context in the cache
func (c *Cache) Set(key string, value *cachedContext) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		elem.Value.(*cacheEntry).value = value
		c.list.MoveToFront(elem)
		return
	}

	entry := &cacheEntry{key: key, value: value}
	elem := c.list.PushFront(entry)
	c.items[key] = elem

	if c.list.Len() > c.cap {
		oldest := c.list.Back()
		if oldest != nil {
			c.list.Remove(oldest)
			delete(c.items, oldest.Value.(*cacheEntry).key)
		}
	}
}

// Remove removes a key from the cache
func (c *Cache) Remove(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if elem, ok := c.items[key]; ok {
		c.list.Remove(elem)
		delete(c.items, key)
	}
}

// Len returns the number of items in the cache
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.list.Len()
}

// Clear removes all items from the cache
func (c *Cache) Clear() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items = make(map[string]*list.Element)
	c.list = list.New()
}
