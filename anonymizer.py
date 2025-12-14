import logging
import pandas as pd
import json
import os
import sys
import hashlib
import pydicom
import re
import yaml
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

    def __init__(self, config_section="variables", file_name="/recipes/variables.yaml"):
        # Get the private tags from the varaibles.yaml file
        self.variables_config = Config(config_section, file_name=file_name)
        self.PatientName = self.variables_config["PatientName"]
        self.ProfileName = self.variables_config["ProfileName"]
        self.ProjectName = self.variables_config["ProjectName"]
        self.TrialName = self.variables_config["TrialName"]
        self.SiteName = self.variables_config["SiteName"]
        self.SiteID = self.variables_config["SiteID"]

        # Paths to the recipes that are mounted in the digione infrastructure docker compose volumes.
        self.recipe_path = "/recipes/recipe.dicom"
        self.patient_lookup_csv = "/recipes/patient_lookup.csv"
        self.ROI_normalization_path = "/recipes/ROI_normalization.yaml"
        
    @staticmethod
    def hash_func(item, value, field, dicom):
        return hashlib.md5(value.encode()).hexdigest()[:16]

    @staticmethod
    def patient_mapping(csv_path):
        df = pd.read_csv(csv_path)
        def lookup(item, value, field, dicom):
            patient_id = dicom.PatientID
            matched = df.loc[df['original'] == patient_id, 'new']
            if matched.empty:
                raise ValueError(f"PatientID: '{patient_id}' not found in patient lookup CSV. Stopping the pipeline for this patient")
            return matched.values[0]
        return lookup

    @staticmethod
    def current_date(field, value, item, dicom):
        now = datetime.now()
        return f"deid: {now.strftime('%d%m%Y:%H%M%S')}"


    def create_and_clear_output_folder(self, input_folder):
        output_base_path = "/app/anonimised_folder"
        folder_name = os.path.basename(input_folder)
        self.output_folder = os.path.join(output_base_path, f"anonimised_{folder_name}")

        if not os.path.exists(self.output_folder):
            os.makedirs(self.output_folder)
            logger.info(f"Output folder created: {self.output_folder}")
            return
        for filename in os.listdir(self.output_folder):
            file_path = os.path.join(self.output_folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                
        logging.info(f"Removed the files in {self.output_folder}")

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

    def find_rtstruct_files(self, folder_path):
        """
        Find all RTSTRUCT files in a folder and return a list of file paths.
        """
        rtstruct_files = []

        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.lower().endswith(".dcm"):
                    try:
                        ds = pydicom.dcmread(entry.path, stop_before_pixels=True)
                        if getattr(ds, "Modality", "") == "RTSTRUCT":
                            rtstruct_files.append(entry.path)
                    except Exception:
                        continue

        return rtstruct_files

    def ROI_normalization(self, folder_path):
        """
        Normalize ROI names in all RTSTRUCT files in the folder using the YAML mapping.
        """
        
        # Load ROI map from YAML
        with open(self.ROI_normalization_path) as f:
            roi_map = yaml.safe_load(f)

        compiled_map = {
            canonical: [re.compile(p, re.IGNORECASE) for p in patterns]
            for canonical, patterns in roi_map.items()
        }

        rtstruct_paths = self.find_rtstruct_files(folder_path)
        if not rtstruct_paths:
            logging.warning(f"No RTSTRUCT files found in {folder_path}")
            return 

        for rtstruct_path in rtstruct_paths:
            ds = pydicom.dcmread(rtstruct_path, stop_before_pixels=True)

            for roi in ds.StructureSetROISequence:
                original_raw = roi.ROIName
                original = original_raw.strip()

                normalized = None

                for canonical, regex_list in compiled_map.items():
                    if any(regex.search(original) for regex in regex_list):
                        normalized = canonical
                        break

                if normalized and original_raw != normalized:
                    roi.ROIName = normalized
                elif normalized is None:
                    logging.warning(f"No ROI map found for '{original_raw}' in file {rtstruct_path}")

            ds.save_as(rtstruct_path)

        
    def anonymize(self, input_folder, recipe_path, patient_lookup_csv):
        logging.info(f"Start anonymizing: {input_folder}")

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
        
        # Turn logger on again
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

            output_path = os.path.join(self.output_folder, f"anonymised_DICOM_{idx}.dcm")
            
            try:
                dicom_obj.save_as(output_path)
            except Exception as e:
                logger.error(f"Failed to save DICOM {idx}: {e}")
            
        logger.info(f"Anonymization completed. Files saved to: {self.output_folder}")
        
    
    def run(self, ch, method, properties, body, executor):
        ch.basic_ack(delivery_tag=method.delivery_tag)
                
        # Get the data from the rabbitMQ message
        message_data = json.loads(body.decode("utf-8"))
        input_folder = message_data.get('input_folder_path')
        
        self.create_and_clear_output_folder(input_folder)
        
        try:
            self.ROI_normalization(input_folder)
            self.anonymize(input_folder, self.recipe_path, self.patient_lookup_csv)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return
        
        # Send a message to the next queue.
        if Config("anonymizer")["send_queue"] != None:
            self.send_next_queue(Config("anonymizer")["send_queue"], self.output_folder)
            
# Main runner
if __name__ == "__main__":
    rabbitMQ_config = Config("anonymizer")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    anonymizer = Anonymizer()
    cons.start_consumer(callback=anonymizer.run)

