import os
from aspose.email.storage.pst import PersonalStorage

def test():
    pst = PersonalStorage.from_file(r"c:\bento\prg\app-outlook\archive.pst")
    folder = pst.root_folder
    
    for msg_info in folder.enumerate_messages():
        print("Found msg:", msg_info.subject)
        try:
            msg = pst.extract_message(msg_info)
            print("Sender:", msg.sender_representative_name)
            print("Date:", msg.client_submit_time)
            print("Att count:", len(msg.attachments))
            for att in msg.attachments:
                print("  Att Name:", att.long_file_name or att.display_name or att.file_name)
                # Test extracting bytes
                temp_path = "test_att.tmp"
                att.save(temp_path)
                with open(temp_path, "rb") as f:
                    data = f.read()
                print("  Att Size:", len(data))
        except Exception as e:
            print("Error:", e)
        break
    
    # Also check subfolders if root has no messages
    if folder.content_count == 0:
        for sub in folder.get_sub_folders():
            print("Checking subfolder:", sub.display_name)
            for msg_info in sub.enumerate_messages():
                print("Found msg down here:", msg_info.subject)
                
                try:
                    msg = pst.extract_message(msg_info)
                    print("Sender:", msg.sender_representative_name)
                    print("Date:", msg.client_submit_time)
                    print("Date iso:", msg.client_submit_time.isoformat() if hasattr(msg.client_submit_time, 'isoformat') else str(msg.client_submit_time))
                    print("Att count:", len(msg.attachments))
                    for att in msg.attachments:
                        print("  Att Name:", att.long_file_name or att.display_name or att.file_name)
                        temp_path = "test_att.tmp"
                        att.save(temp_path)
                        with open(temp_path, "rb") as f:
                            data = f.read()
                        print("  Att Size:", len(data))
                        os.remove(temp_path)
                except Exception as e:
                    print("Error:", e)
                break
            break

    pst.dispose()

if __name__ == "__main__":
    test()
