import os
from pydicom import dcmread
from pynetdicom import AE, StoragePresentationContexts

"""This class is made to send dicom data to a XNAT server. The adding_treatment_site method is made to hardcode the treatment sides where we want filter on in the XNAT projects.
to_XNAT is for sending data to the XNAT server. Important thing to note XNAT filters data on Patient ID and Patient's name, which means that if the data received has the same
patient name and the same patient id then it sorts it into the same data package."""

class send_DICOM:
    def adding_treatment_site(self, root_folder, patient_ids: list, treatment_sites: list):
        
        for ids, treatment_site, folder in zip(patient_ids, treatment_sites, os.listdir(root_folder)):
            folder_path = os.path.join(root_folder, folder)
            
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                ds = dcmread(file_path)
                ds.PatientID = ids
                ds.BodyPartExamined  = treatment_site
                ds.save_as(file_path)

    def to_XNAT(self, root_folder, ports):
        ae = AE()
        ae.requested_contexts = StoragePresentationContexts

        for folder in os.listdir(root_folder):
            folder_path = os.path.join(root_folder, folder)
            
            ds = dcmread(os.path.join(folder_path, os.listdir(folder_path)[0]))
            treatment_site = ds.BodyPartExamined
            
            port = ports[treatment_site]["Port"]
            Title = ports[treatment_site]["Title"]
            
            
            assoc = ae.associate('localhost', port, ae_title = Title)
            
            if assoc.is_established:
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    
                    ds = dcmread(file_path)
                    assoc.send_c_store(ds)
                
                assoc.release()
            else:
                print("Association failes")

if __name__ == "__main__":
    folder = "short_anonimised_folder"
    patient_ids = ["Tom", "Tom"]
    treatment_sites = ["LUNG", "KIDNEY"]
    ports = {
        "LUNG": {"Title": "LUNG", "Port": 8104},
        "KIDNEY": {"Title": "KIDNEY", "Port": 8104}
    }
    
    xnat_pipeline = send_DICOM()
    xnat_pipeline.adding_treatment_site(folder, patient_ids, treatment_sites)
    xnat_pipeline.to_XNAT(folder, ports)
    