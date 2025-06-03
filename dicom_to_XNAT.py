import os
from pydicom import dcmread
from pynetdicom import AE, StoragePresentationContexts

ae = AE()
ae.requested_contexts = StoragePresentationContexts
assoc = ae.associate('localhost', 8104, ae_title='XNAT')

dicom_dir = (r'anonimised_folder\anonimised_data')

if assoc.is_established:
    for file in os.listdir(dicom_dir):
        ds = dcmread(os.path.join(dicom_dir, file))

        status = assoc.send_c_store(ds)
        
    assoc.release()
else:
    print("Association failed")