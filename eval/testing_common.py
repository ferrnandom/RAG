from eval.common import chunk_key
from source.vector_store import VectorStorage

store = VectorStorage()
chunks = store.all_chunks()
keys = [chunk_key(c["metadata"]) for c in chunks]
assert len(keys) == len(set(keys)), "keys are not unique"
print(len(keys), "chunks,", keys[0])
store.close()
