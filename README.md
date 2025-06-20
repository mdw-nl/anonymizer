The difference between this version and CTP:
- The hashuid is probably based on a different hash so the produced value is not the same. The hash used is the only hash in the deid package that gives a deterministic uid answer.
- For the hashuid needs to be given a prefix this is it the org_id. This is is the only variable that needs to be hard coded into the recipe.dicom.
- A custom function has been created for the normal hash function, this is done with the MD5 hash which is probably different then the CTP hash, it takes the first 16 characters.
- For the StructureSetLabel the same custom hash function has been used. This causes the length of the computed value to be different then the computed CTP value.
- PatientID is replaced by a custom function that does a look up in a CSV file. The CSV file is called patient_custom.csv
- VerifyingObserverName, PersonName instead of an if statement that checks if the value is empty is it just replaced. This is because deid does not support if statements in the recipe.
- 0018, 0020, curves, overlays, 0028, are groups and deid does support actions on groups, so line 1050 until 1056 from anonymizer.properties are omitted.
- In CTP the remove privategroups is disabled however, here it is done before the private tags are added.
- Deid does not support adding or manipulating private tags, so for this the recipe does not work and it needs to be coded into the python script. Pydicom does not allow for direct control over the name of the private tag. However you can add a dictionary with the names of the of the private tag, this can only be seen with the pydicom package.
- DeidentificationMethod does not contain profilename anymore, profilename is added as a private tag.

