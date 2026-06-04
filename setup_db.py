import mariadb
import sys
from configparser import ConfigParser

def run_initial_setup(root_password):
	try:
		# Verbindung als Root
		conn = mariadb.connect(
			host="localhost",
			user="root",
			password=root_password
		)
		cur = conn.cursor()

		# 1. User anlegen
		cur.execute("CREATE USER IF NOT EXISTS 'va_user'@'localhost' IDENTIFIED BY 'analyzer_pw123'")
		
		# 2. DB anlegen
		cur.execute("CREATE DATABASE IF NOT EXISTS forensic_analyzer")
		
		# 3. Rechte vergeben
		cur.execute("GRANT ALL PRIVILEGES ON forensic_analyzer.* TO 'va_user'@'localhost'")
		cur.execute("FLUSH PRIVILEGES")
		
		print("[✔] Datenbank und User 'va_user' erfolgreich konfiguriert.")
		conn.close()
		
		# 4. mariadb.ini automatisch aktualisieren
		update_config('va_user', 'analyzer_pw123')

	except mariadb.Error as e:
		print(f"[✘] Fehler: {e}")

def update_config(user, pwd):
	config = ConfigParser()
	config.read('config/mariadb.ini')
	if not config.has_section('database'): config.add_section('database')
	
	config.set('database', 'user', user)
	config.set('database', 'password', pwd)
	config.set('database', 'host', 'localhost')
	config.set('database', 'port', '3306')
	
	with open('config/mariadb.ini', 'w') as f:
		config.write(f)
	print("[✔] mariadb.ini wurde aktualisiert.")

if __name__ == "__main__":
	root_pw = input("Bitte MariaDB Root-Passwort für das Setup eingeben: ")
	run_initial_setup(root_pw)