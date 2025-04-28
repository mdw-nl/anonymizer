from config_handler import Config
from consumer import Consumer
import logging
import pandas as pd
import json
import time
import os
import pydicom
import sys
from deid.dicom import get_files, replace_identifiers
from deid.config import DeidRecipe
from deid.dicom import get_identifiers

def custom_func(item, value, field, dicom):
    # Get the current PatientID from the DICOM file
    dicom_path = os.path.join("dicomdata", "RS.PYTIM05_.dcm")
    ds = pydicom.dcmread(dicom_path)
    PatientID = ds.PatientID
    
    # Create pandas dataframe from the recipe CSV file and get the new value
    df = pd.read_csv('recipe_CSV.csv')
    new_value = df.loc[df['original'] == PatientID, 'new'].values[0]
    
    return new_value


def anonymize(ch, method, properties, body, executor):
    """The anonymize function that anonymizes the data, in the consumer method"""
    message_str = body.decode("utf-8")
    message_data = json.loads(message_str)
    input_folder = message_data.get('input_folder_path')
    output_folder = message_data.get('output_folder_path')
    recipe_path = message_data.get('recipe_path')
    action = message_data.get('action')
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        logging.warning(f"Output folder did not exist, created: {output_folder}")

    if action != "anonymize":
        logging.warning(f"Action {action} is not supported. Skipping message.")
        return
    
    if not all([input_folder, output_folder, recipe_path]):
        logging.error("Missing one or more required fields in message.")
        ch.basic_nack(delivery_tag=method.delivery_tag)
        return
    
    # This removes all the files in the output folder, this is only for testing purposes
    for filename in os.listdir(output_folder):
        file_path = os.path.join(output_folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    
    dicom_files = list(get_files(input_folder))
    recipe = DeidRecipe(deid=recipe_path)
    
    # Temperarily suppress stdout and stderr to avoid cluttering the console
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
    
    # Update the items so it contains the generate_uid function
    items = get_identifiers(dicom_files)
    for item in items:
        items[item]["custom_func"] = custom_func
         
    updated = replace_identifiers(dicom_files=dicom_files, deid=recipe, ids=items)
    
    for idx, dicom_obj in enumerate(updated, 1):
        output_filename = f"anonymised_CT.PYTIM05_{idx}.dcm"
        output_path = os.path.join(output_folder, output_filename)
        dicom_obj.save_as(output_path)
    
    # Restore stdout and stderr  
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__  
    
    logging.info(f"Anonymization completed. Files from {input_folder} are anonymized and saved to {output_folder}.")
        
    
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

if __name__ == "__main__":
    rabbitMQ_config = Config("rabbitMQ")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    cons.send_message()
    cons.start_consumer(callback=anonymize)

