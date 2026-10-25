
import pyotp

secreto = pyotp.random_base32()

print("\nSecreto para ADMIN_TOTP_SECRET:")
print(secreto)
print("\nIntroduce esta clave manualmente en tu aplicación autenticadora.")
print("Nombre de la cuenta: Linneo Admin")
print("Tipo de clave: basada en tiempo (TOTP)")
