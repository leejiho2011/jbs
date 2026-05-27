import os
import yaml
import argparse
import json
import sys
from cryptography.fernet import Fernet

class SecureChatManager:
    def __init__(self, filename="gemini.yml.enc"):
        self.filename = filename

    def generate_key(self):
        """새로운 암호화 키를 생성합니다."""
        key = Fernet.generate_key().decode()
        print(f"KEY_START\n{key}\nKEY_END")

    def get_cipher(self, key_str):
        """키 유효성을 검사하고 Fernet 객체를 반환합니다."""
        try:
            return Fernet(key_str.encode())
        except Exception:
            print("❌ 오류: 유효하지 않은 키 형식입니다.")
            return None

    def encrypt_chat(self, key_str, data_list):
        """대화 기록(리스트)을 YAML로 변환한 뒤 암호화하여 파일로 저장합니다."""
        cipher = self.get_cipher(key_str)
        if not cipher:
            return

        try:
            # 1. 대화 데이터를 YAML 포맷의 문자열로 변환
            yaml_data = yaml.dump(data_list, allow_unicode=True, sort_keys=False)
            
            # 2. 문자열을 byte로 인코딩 후 암호화
            encrypted_data = cipher.encrypt(yaml_data.encode('utf-8'))
            
            # 3. 암호화된 데이터를 파일(.enc)에 저장
            with open(self.filename, 'wb') as f:
                f.write(encrypted_data)
                
            print(f"🔒 성공: 데이터가 암호화되어 '{self.filename}'에 저장되었습니다.")
            
        except Exception as e:
            print(f"❌ 암호화 중 오류 발생: {e}")

    def decrypt_chat(self, key_str):
        """암호화된 파일을 읽어 복호화한 뒤 YAML 내용을 출력합니다."""
        if not os.path.exists(self.filename):
            print(f"❌ 오류: '{self.filename}' 파일을 찾을 수 없습니다.")
            return

        cipher = self.get_cipher(key_str)
        if not cipher:
            return

        try:
            # 1. 암호화된 파일 읽기
            with open(self.filename, 'rb') as f:
                encrypted_data = f.read()
            
            # 2. 복호화
            decrypted_data = cipher.decrypt(encrypted_data)
            
            # 3. byte를 문자열로 디코딩
            yaml_text = decrypted_data.decode('utf-8')
            
            print(f"🔓 [복호화 성공]")
            print("-" * 40)
            print(yaml_text)
            print("-" * 40)
            
        except Exception:
            print("❌ 복호화 실패: 키가 일치하지 않거나 파일이 손상되었습니다.")

def main():
    parser = argparse.ArgumentParser(description="Gemini CLI - Secure Chat Skill")
    parser.add_argument("action", choices=["keygen", "encrypt", "decrypt"], help="Action to perform")
    parser.add_argument("-k", "--key", type=str, help="Encryption/Decryption key")
    parser.add_argument("-d", "--data", type=str, help="JSON string data to encrypt")
    parser.add_argument("-f", "--file", type=str, default="gemini.yml.enc", help="Filename to use")

    args = parser.parse_args()
    manager = SecureChatManager(args.file)

    if args.action == "keygen":
        manager.generate_key()
        
    elif args.action == "encrypt":
        if not args.key:
            print("❌ 오류: 키가 필요합니다.")
            return
        if not args.data:
            print("❌ 오류: 암호화할 데이터(JSON)가 필요합니다.")
            return
        try:
            data_list = json.loads(args.data)
            manager.encrypt_chat(args.key, data_list)
        except json.JSONDecodeError:
            print("❌ 오류: 데이터가 유효한 JSON 형식이 아닙니다.")
        
    elif args.action == "decrypt":
        if not args.key:
            print("❌ 오류: 키가 필요합니다.")
            return
        manager.decrypt_chat(args.key)

if __name__ == "__main__":
    main()
