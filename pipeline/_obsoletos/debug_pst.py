import os
import sys
import logging
from aspose.email.storage.pst import PersonalStorage

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("debug_pst")

def debug_pst(pst_path: str):
    pst = PersonalStorage.from_file(pst_path)
    
    total_messages = 0
    folders_to_process = [pst.root_folder]
    
    while folders_to_process:
        folder = folders_to_process.pop()
        folder_name = getattr(folder, 'display_name', 'Unknown')
        
        ignored_folders = ['itens excluídos', 'deleted items', 'lixo eletrônico', 'junk e-mail', 'rascunhos', 'drafts', 'spam']
        if any(ignored in folder_name.lower() for ignored in ignored_folders):
            logger.info(f"Skipping ignored: {folder_name}")
            continue
            
        count = folder.content_count
        logger.info(f"Folder '{folder_name}' has {count} items.")
        
        # How many does enumerate_messages yield?
        enum_count = 0
        try:
            for m in folder.enumerate_messages():
                enum_count += 1
        except Exception as e:
            logger.error(f"Error enumerating in {folder_name}: {e}")
            
        logger.info(f"Folder '{folder_name}' yielded {enum_count} messages from enumerate_messages().")
        total_messages += enum_count
        
        for subfolder in folder.get_sub_folders():
            folders_to_process.append(subfolder)
            
    logger.info(f"Total enumerated messages: {total_messages}")

if __name__ == "__main__":
    debug_pst("c:/bento/prg/app-outlook/luis.bento@nacionalindustria.com.br - Nacional.ost")
