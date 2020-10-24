from argon2 import PasswordHasher

print(PasswordHasher().hash(input("Enter your password. This will not be stored.\n> ")))
