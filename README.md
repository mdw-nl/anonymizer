This repository provides an **Anonymizer class** that processes DICOM files according to configurable recipes, anonymizes sensitive information, and sends the results forward in a processing pipeline via **RabbitMQ**.

---

## What It Does

This anonymizer class takes a folder with DICOM files and anonymizes them according to the configured **recipes**.  

- The **`patient_lookup.csv`** changes the `PatientID` from the old to the new.  
  - If the patient ID is **not** found in this CSV, anonymization (and the pipeline) will stop.  
- The **`recipe.dicom`** file tells the script how to anonymize.  
- The **`digioneinfrastructure`** repository provides the shared `recipes` folder.  
  - If you don’t use the `digioneinfrastructure` repository, update the paths:
    - `self.recipe_path`
    - `self.patient_lookup_csv`
- Private tags are added via **`variables.yaml`**.  
  - The `config_handler` has been updated to handle YAML files with different names.  
  - For now, `variables.yaml` is stored in this repository, but it may later be moved to `digioneinfrastructure` and shared via Docker volumes.  
- By default, the output folder is **cleared before writing new data**.  
  - This ensures clean runs, but might need to be disabled depending on use cases.  
- After anonymization, a **RabbitMQ message** is sent with the `messenger` class.  
  - The message contains the data folder path and the RabbitMQ queue.  
  - The next queue is determined via the `digioneinfrastructure/config.yaml` file.  

---

## Differences Compared to CTP

This anonymizer is based on the [deid](https://pydicom.github.io/deid/) package, but with custom functions and adjustments to replicate/replace parts of the CTP pipeline:

- **Hash UID**
  - Uses a different hashing algorithm than CTP.
  - Deterministic UID hash is provided by `deid`.
  - Requires a prefix (`org_id`) hardcoded in `recipe.dicom`.

- **Custom Hash Function**
  - MD5-based hash, truncated to the first 16 characters.
  - Used for general hashing and `StructureSetLabel`.
  - Results differ in length/value compared to CTP.

- **Patient ID Lookup**
  - Replaced via a lookup in `patient_lookup.csv`.
  - File is named `patient_custom.csv`.

- **Name Handling**
  - `VerifyingObserverName` and `PersonName` are **always replaced** (no `if` condition, since `deid` does not support conditional rules).

- **Unsupported Groups**
  - `0018, 0020, curves, overlays, 0028` are DICOM groups that `deid` cannot handle.  
  - Lines 1050–1056 from `anonymizer.properties` are therefore omitted.

- **Private Tags**
  - In CTP, private group removal is disabled.  
  - Here, private groups are **removed first** before custom private tags are added.  
  - `deid` does not support adding/manipulating private tags → handled directly in Python.  
  - `pydicom` does not allow renaming private tags, but a dictionary can be defined so tags show up with meaningful names when viewed via `pydicom`.

- **DeidentificationMethod**
  - No longer contains `profilename`.  
  - Instead, `profilename` is stored as a private tag.

---

## Repository Structure

- `anonymizer.py` → Main anonymizer class.  
- `variables.yaml` → Defines private tag values (`PatientName`, `ProfileName`, `ProjectName`, etc.).  
- `recipe.dicom` → Deid anonymization recipe file.  
- `patient_lookup.csv` → Maps original patient IDs to new ones.  
- `RabbitMQ_messenger.py` → Sends results to the next RabbitMQ queue.  
- `config_handler.py` → Handles YAML-based configs.  
- `consumer.py` → RabbitMQ consumer logic. 

