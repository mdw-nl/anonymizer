from config_handler import Config
from consumer import Consumer
import logging
import pandas as pd
import json
import os
import sys
import hashlib
from deid.dicom import get_files, replace_identifiers
from deid.config import DeidRecipe
from deid.dicom import get_identifiers
from pydicom.dataset import Dataset
from pydicom.datadict import add_private_dict_entries
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()


def hash_func(item, value, field, dicom):
    """Hash the input value and return a shortened version."""
    return hashlib.md5(value.encode()).hexdigest()[:16]

def patient_mapping(CSV_mapping):
    """Returns a lookup function to map PatientIDs using a CSV file."""
    df = pd.read_csv(CSV_mapping)
    
    def CSV_lookup_func(item, value, field, dicom):
        PatientID = dicom.PatientID         
         # Get the new value
        new_value = df.loc[df['original'] == PatientID, 'new'].values[0]              
        return new_value
    
    return CSV_lookup_func

def DeIdentificationMethod(field, value, item, dicom):
    now = datetime.now()
    date_str = now.strftime("%d%m%Y")
    time_str = now.strftime("%H%M%S")
    return f"deid: {date_str}:{time_str}"

def clear_output_folder(folder_path):
    """Delete all files in the output folder (for testing purposes)."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        logger.warning(f"Output folder did not exist, created: {folder_path}")
        return

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)

def suppress_output():
    """Temporarily suppress stdout and stderr."""
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')


def restore_output():
    """Restore stdout and stderr."""
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__


# Main anonymization function
def anonymize(ch, method, properties, body, executor):
    message_str = body.decode("utf-8")
    
    message_data = json.loads(message_str)
    input_folder = message_data.get('input_folder_path')
    output_folder = message_data.get('output_folder_path')
    recipe_path = message_data.get('recipe_path')
    action = message_data.get('action')
    patient_lookup_csv = message_data.get('patient_lookup')
    
    # Get the variables from the yaml file
    variables_config = Config("variables")
    PatientName = variables_config["PatientName"]
    ProfileName = variables_config["ProfileName"]
    ProjectName = variables_config["ProjectName"]
    TrialName = variables_config["TrialName"]
    SiteName = variables_config["SiteName"]
    SiteID = variables_config["SiteID"]
    
    if action != "anonymize":
        logging.warning(f"Action {action} is not supported. Skipping message.")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
        
    clear_output_folder(output_folder) 
    dicom_files = list(get_files(input_folder))
    recipe = DeidRecipe(deid=recipe_path)
    
    # Temperarily suppress stdout and stderr to avoid cluttering the console
    suppress_output()
    
    # Update the items so it contains the generate_uid function
    items = get_identifiers(dicom_files,  expand_sequences=False)    
    for item in items:
        items[item]["CSV_lookup_func"] = patient_mapping(patient_lookup_csv)
        items[item]["hash_func"] = hash_func
        items[item]["DeIdentificationMethod"] = DeIdentificationMethod
        items[item]["PatientName"] = PatientName
         
    updated = replace_identifiers(dicom_files=dicom_files, deid=recipe, ids=items)
    
    # Restore stdout and stderr  
    restore_output()  

    # Names of the private tags
    entries = {
        0x10011001:( "SH", "1", "ProfileName", ""),
        0x10011002:( "SH", "1", "ProjectName", ""),
        0x10011003:( "SH", "1", "TrialName", ""),
        0x10011004:( "SH", "1", "SiteName", ""),
        0x10011005:( "SH", "1", "SiteID", ""),
    }
    
    for idx, dicom_obj in enumerate(updated, 1):
        
        # Add private tags
        block = dicom_obj.private_block(0x1001, 'Deid', create=True)
        block.add_new(0x01, "SH", ProfileName)
        block.add_new(0x02, "SH", ProjectName)
        block.add_new(0x03, 'SH', TrialName)
        block.add_new(0x04, 'SH', SiteName)
        block.add_new(0x05, 'SH', SiteID)
        
        add_private_dict_entries("Deid", entries)

        output_filename = f"anonymised_DICOM_{idx}.dcm"
        output_path = os.path.join(output_folder, output_filename)
        dicom_obj.save_as(output_path)
        
    ch.basic_ack(delivery_tag=method.delivery_tag)
    logging.info(f"Anonymization completed. Files from {input_folder} are anonymized and saved to {output_folder}.")
        

if __name__ == "__main__":
    
    rabbitMQ_config = Config("rabbitMQ")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    cons.send_message("messages")
    cons.start_consumer(callback=anonymize)

