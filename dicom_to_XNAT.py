import os
from pydicom import dcmread
from pynetdicom import AE, StoragePresentationContexts

def adding_treatment_site():
    root_folder = 'anonimised_folder'

    patient_ids = ["Tom1", "Tom2"]
    treatment_sites = ["LUNG1", "KIDNEY1"]

    for ids, treatment_site, folder in zip(patient_ids, treatment_sites, os.listdir(root_folder)):
        folder_path = os.path.join(root_folder, folder)
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            ds = dcmread(file_path)
            ds.PatientID = ids
            ds.BodyPartExamined  = treatment_site
            ds.save_as(file_path)

def to_XNAT():
    root_folder = 'anonimised_folder'

    ae = AE()
    ae.requested_contexts = StoragePresentationContexts

    ports = {
        "LUNG1": {"Title": "LUNG1", "Port": 8104},
        "KIDNEY1": {"Title": "KIDNEY1", "Port": 8104}
    }

    for folder in os.listdir(root_folder):
        folder_path = os.path.join(root_folder, folder)
        
        ds = dcmread(os.path.join(folder_path, os.listdir(folder_path)[0]))
        treatment_site = ds.BodyPartExamined
        
        print(ds.PatientID)
        print(treatment_site)
        
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
    to_XNAT()
    