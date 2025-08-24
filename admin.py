import redis

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
redis_client.hset("user:admin", mapping={
    "password": "admin",
    "email": "admin@example.com",
    "role": "admin"
})
print("Użytkownik admin utworzony!")
