import extract_msg
import os
import base64

def analyze_msg(file_path):
    print(f"Analyzing MSG file: {file_path}")
    msg = extract_msg.Message(file_path)
    
    print("\n=== Basic Information ===")
    print(f"Subject: {msg.subject}")
    print(f"From: {msg.sender}")
    print(f"To: {msg.to}")
    
    print("\n=== Body Properties ===")
    print("Has RTF:", hasattr(msg, '_rtf'))
    
    print("\nPlain Body Type:", type(msg.body))
    print("Plain Body Preview:")
    print("---START OF PLAIN BODY---")
    print(msg.body[:500])
    print("---END OF PLAIN BODY---")
    
    print("\nHTML Body Preview:")
    print("---START OF HTML BODY---")
    if msg.htmlBody:
        try:
            html_content = msg.htmlBody.decode('utf-8', errors='ignore')
            print(html_content[:1000])
        except Exception as e:
            print(f"Error decoding HTML body: {e}")
    else:
        print("No HTML body found")
    print("---END OF HTML BODY---")
    
    print("\nRTF Body Preview:")
    print("---START OF RTF BODY---")
    if msg.rtfBody:
        try:
            rtf_content = msg.rtfBody.decode('utf-8', errors='ignore')
            print(rtf_content[:1000])
        except Exception as e:
            print(f"Error decoding RTF body: {e}")
    else:
        print("No RTF body found")
    print("---END OF RTF BODY---")
    
    print("\n=== Images ===")
    for att in msg.attachments:
        if att.longFilename and 'image' in att.longFilename.lower():
            print(f"Found image: {att.longFilename}")
            print(f"Content-ID: {att.cid if hasattr(att, 'cid') else 'No CID'}")
    
    print("\n=== Available Attributes ===")
    for attr in dir(msg):
        if not attr.startswith('_'):
            try:
                value = getattr(msg, attr)
                if not callable(value):
                    print(f"{attr}: {type(value)}")
            except Exception as e:
                print(f"{attr}: Error accessing - {str(e)}")

if __name__ == "__main__":
    file_path = "FACTURE NO. 7005451.msg"
    if os.path.exists(file_path):
        analyze_msg(file_path)
    else:
        print(f"File not found: {file_path}")
