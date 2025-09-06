import pinecone
pinecone.init(api_key="pcsk_3gXfsx_PBHnM3f5S7eP5DZGMGVAULCKQRfbuaGghLLsWUkHqAqjpxh4EZ5YAotmzjYNErN", environment="us-east-1-aws")
print(pinecone.list_indexes())
