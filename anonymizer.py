import logging
import pandas as pd
import json
import os
import sys
import hashlib
from datetime import datetime
from deid.dicom import get_files, replace_identifiers, get_identifiers
from deid.config import DeidRecipe
from pydicom.datadict import add_private_dict_entries
from config_handler import Config
from consumer import Consumer
from RabbitMQ_messenger import messenger

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

class Anonymizer:

    def __init__(self, config_section="variables", file_name="variables.yaml"):
        # Get the private tags from the varaibles.yaml file
        self.variables_config = Config(config_section, file_name=file_name)
        self.PatientName = self.variables_config["PatientName"]
        self.ProfileName = self.variables_config["ProfileName"]
        self.ProjectName = self.variables_config["ProjectName"]
        self.TrialName = self.variables_config["TrialName"]
        self.SiteName = self.variables_config["SiteName"]
        self.SiteID = self.variables_config["SiteID"]

        # Paths to the recipes that are mounted in the digione infrastructure docker compose volumes.
        self.recipe_path = "app/recipes/recipe.dicom"
        self.patient_lookup_csv = "app/recipes/patient_lookup.csv"
        
    @staticmethod
    def hash_func(item, value, field, dicom):
        return hashlib.md5(value.encode()).hexdigest()[:16]

    @staticmethod
    def patient_mapping(csv_path):
        df = pd.read_csv(csv_path)
        def lookup(item, value, field, dicom):
            patient_id = dicom.PatientID
            return df.loc[df['original'] == patient_id, 'new'].values[0]
        return lookup

    @staticmethod
    def current_date(field, value, item, dicom):
        now = datetime.now()
        return f"deid: {now.strftime('%d%m%Y:%H%M%S')}"

    @staticmethod
    def clear_output_folder(folder_path):
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.warning(f"Output folder created: {folder_path}")
            return
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
        logging.info(f"Removed the files in {folder_path}")

    @staticmethod
    def suppress_output():
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')

    @staticmethod
    def restore_output():
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
    
    def send_next_queue(self, queue, data_folder):
        message_creator = messenger()
        message_creator.create_message_next_queue(queue, data_folder)

    def anonymize(self, input_folder, output_folder, recipe_path, action, patient_lookup_csv):

        if not os.path.exists(output_folder):
            logger.info(f"Creating output folder: {output_folder}")
            os.makedirs(output_folder)
        else:
            self.clear_output_folder(output_folder)

        dicom_files = list(get_files(input_folder))
        recipe = DeidRecipe(deid=recipe_path)

        # Suppreses the logger
        self.suppress_output()
        
        # Applies the methods previously defined into the items 
        items = get_identifiers(dicom_files, expand_sequences=False)
        for item in items:
            items[item].update({
                "CSV_lookup_func": self.patient_mapping(patient_lookup_csv),
                "hash_func": self.hash_func,
                "DeIdentificationMethod": self.current_date,
                "PatientName": self.PatientName
            })
        updated = replace_identifiers(dicom_files=dicom_files, deid=recipe, ids=items)
        self.restore_output()

        # Define the private tags
        private_entries = {
            0x10011001: ("SH", "1", "ProfileName"),
            0x10031001: ("SH", "1", "ProjectName"),
            0x10051001: ("SH", "1", "TrialName"),
            0x10071001: ("SH", "1", "SiteName"),
            0x10091001: ("SH", "1", "SiteID"),
        }

        add_private_dict_entries("Deid", private_entries)

        for idx, dicom_obj in enumerate(updated, 1):
            dicom_obj.remove_private_tags()
            dicom_obj.private_block(0x1001, 'Deid', create=True).add_new(0x01, "SH", self.ProfileName)
            dicom_obj.private_block(0x1003, 'Deid', create=True).add_new(0x01, "SH", self.ProjectName)
            dicom_obj.private_block(0x1005, 'Deid', create=True).add_new(0x01, "SH", self.TrialName)
            dicom_obj.private_block(0x1007, 'Deid', create=True).add_new(0x01, "SH", self.SiteName)
            dicom_obj.private_block(0x1009, 'Deid', create=True).add_new(0x01, "SH", self.SiteID)

            output_path = os.path.join(output_folder, f"anonymised_DICOM_{idx}.dcm")
            
            try:
                dicom_obj.save_as(output_path)
            except Exception as e:
                logger.error(f"Failed to save DICOM {idx}: {e}")
            
        logger.info(f"Anonymization completed. Files saved to: {output_folder}")
        
    
    def run(self, ch, method, properties, body, executor):
        # Get the data from the rabbitMQ message
        message_data = json.loads(body.decode("utf-8"))
        input_folder = message_data.get('input_folder_path')
        output_folder = message_data.get('output_folder_path')
        action = message_data.get('action')
        
        if action != "anonymize":
            logger.warning(f"Unsupported action: {action}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        self.anonymize(input_folder, output_folder, self.recipe_path, action, self.patient_lookup_csv)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # Send a message to the next queue.
        self.send_next_queue(Config("anonymizer")["send_queue"], output_folder)
        
        
# Main runner
if __name__ == "__main__":
    rabbitMQ_config = Config("anonymizer")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    anonymizer = Anonymizer()
    cons.start_consumer(callback=anonymizer.run)

