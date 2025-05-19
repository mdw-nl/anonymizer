# anonymizer
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 -e RABBITMQ_DEFAULT_USER=myuser -e RABBITMQ_DEFAULT_PASS=mypassword rabbitmq:3-management

The difference between this version and CTP:
- The hashuid is probably based on a different hash so the produced value is not the same. The hash used is the only hash in the deid package that gives a deterministic uid answer.
- A custom function has been created for the normal hash function, this is done with the MD5 hash which is probably different then the CTP hash, it takes the first 16 characters.
- For the StructureSetLabel the same custom hash function has been used. This causes the length of the computed value to be different then the computed CTP value.
- BlockOwner, ProjectName, TrialName, SiteName, SiteID are excluded cause deid only works with dicom attributes and these do not exist.
- PatientID is replaced by a custom function that does a look up in a CSV file. 
- DeIdentificationMethod is left out cause of some errors, however when CTP is applied this attribute is not added.
- VerifyingObserverName, PersonName instead of an if statement that checks if the value is empty is it just replaced. This is because deid does not support if statements in the recipe.
- 0018, 0020, curves, overlays, privategroups, 0028, unspecifiedelements are not actual attributes so they are omitted. 