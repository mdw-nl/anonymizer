import pydicom

def load_dicom(file_path):
    try:
        return pydicom.dcmread(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def compare_dicom(ds1, ds2):
    keys1 = set(ds1.dir())
    keys2 = set(ds2.dir())

    all_keys = sorted(keys1.union(keys2))
    differences = []

    for key in all_keys:
        if key not in keys1:
            differences.append(f"Tag '{key}' only in second file.")
            continue
        # if key not in keys2:
        #     differences.append(f"Tag '{key}' only in first file.")
        #     continue

        val1 = getattr(ds1, key, None)
        val2 = getattr(ds2, key, None)

        # Ignore large binary data like pixel arrays or sequence length mismatches
        if isinstance(val1, bytes) or isinstance(val2, bytes):
            continue
        if val1 != val2:
            differences.append(f"\nTag '{key}':\n  File1: {val1}\n  File2: {val2}")

    if not differences:
        print("✅ The DICOM files are identical in compared tags.")
    else:
        print("❗ Differences found:")
        for diff in differences:
            print(diff[-150:])

if __name__ == "__main__":
    file1 = r"anonimised_folder\anonimised_data2\anonymised_DICOM_290.dcm"
    file2 = r"CTP_anonimised_data\RTSTRUCT\99999.237795022623052706743555483744140971660"

    ds1 = load_dicom(file1)
    ds2 = load_dicom(file2)

    if ds1 and ds2:
        compare_dicom(ds1, ds2)
