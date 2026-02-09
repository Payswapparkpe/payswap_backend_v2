Public Key for Retailer 
Key Version: 1.0
Generated on: Thu Jan 15 11:19:16 IST 2026
Expires on: Fri Jan 15 11:19:16 IST 2027

Instructions:
1. Use this public key to encrypt your session keys
2. Include keyVersion in each request
3. Keep this key secure

Integration Steps:
1. Generate a random AES key (session key) for each request
2. Encrypt your payload with this AES key
3. Encrypt the AES key with this public RSA key
4. Send both the encrypted payload and encrypted session key
