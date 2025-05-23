import io

import pydicom
from pydicom.datadict import add_private_dict_entries
from pydicom.dataset import Dataset

ds = Dataset()
ds.is_implicit_VR = True
ds.is_little_endian = True

ds.private_block(0x1001, 'Deid', create=True).add_new(0x01, "SH", "ProfileName")
ds.private_block(0x1003, 'Deid', create=True).add_new(0x01, "SH", "ProjectName")
ds.private_block(0x1005, 'Deid', create=True).add_new(0x01, "SH", "TrialName")
ds.private_block(0x1007, 'Deid', create=True).add_new(0x01, "SH", "SiteName")
ds.private_block(0x1009, 'Deid', create=True).add_new(0x01, "SH", "SiteID")

fp = io.BytesIO()
ds.save_as(fp)
ds = pydicom.dcmread(fp, force=True)

private_entries = {
    0x10011001: ("SH", "1", "ProfileName"),
    0x10031001: ("SH", "1", "ProjectName"),
    0x10051001: ("SH", "1", "TrialName"),
    0x10071001: ("SH", "1", "SiteName"),
    0x10091001: ("SH", "1", "SiteID"),
}

add_private_dict_entries("Deid", private_entries)

ds = pydicom.dcmread(fp, force=True)

print(ds)