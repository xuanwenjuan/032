import numpy as np
import io
import struct
import uuid
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


def _encode_dicom_vr(tag_group: int, tag_element: int, vr: str, value_bytes: bytes) -> bytes:
    tag = struct.pack('<HH', tag_group, tag_element)
    vr_bytes = vr.encode('ascii')
    if vr in ('OB', 'OW', 'OF', 'SQ', 'UT', 'UN'):
        header = tag + vr_bytes + b'\x00\x00' + struct.pack('<I', len(value_bytes))
    else:
        header = tag + vr_bytes + struct.pack('<H', len(value_bytes))
    return header + value_bytes


def _pad_to_even(data: bytes) -> bytes:
    if len(data) % 2 == 1:
        return data + b'\x00'
    return data


def _str_to_dicom(s: str) -> bytes:
    return _pad_to_even(s.encode('ascii'))


def _num_to_dicom(val: int, length: int = 4) -> bytes:
    return str(val).zfill(length).encode('ascii')


def generate_dicom_uid() -> str:
    prefix = "1.2.826.0.1.3680043.2.135"
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:12]
    return f"{prefix}.{ts}.{rand}"


def matrix_to_dicom(
    conductivity_matrix: np.ndarray,
    patient_info: Optional[Dict[str, str]] = None,
    study_info: Optional[Dict[str, str]] = None,
    series_info: Optional[Dict[str, str]] = None,
    modality: str = "OT",
    window_center: Optional[float] = None,
    window_width: Optional[float] = None
) -> bytes:
    matrix = np.array(conductivity_matrix, dtype=np.float64)
    rows, cols = matrix.shape
    if window_center is None:
        window_center = float(np.mean(matrix))
    if window_width is None:
        window_width = float(np.max(matrix) - np.min(matrix))
        if window_width <= 0:
            window_width = 1.0
    rescale_slope = window_width / 65535.0 if window_width > 0 else 1.0 / 65535.0
    rescale_intercept = float(np.min(matrix))
    pixel_min = 0
    pixel_max = 65535
    scaled = (matrix - rescale_intercept) / rescale_slope
    scaled = np.clip(scaled, pixel_min, pixel_max)
    pixel_data = scaled.astype(np.uint16).tobytes(order='C')

    if patient_info is None:
        patient_info = {}
    if study_info is None:
        study_info = {}
    if series_info is None:
        series_info = {}

    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")

    sop_instance_uid = generate_dicom_uid()
    study_instance_uid = study_info.get("StudyInstanceUID", generate_dicom_uid())
    series_instance_uid = series_info.get("SeriesInstanceUID", generate_dicom_uid())
    frame_of_ref_uid = generate_dicom_uid()

    meta_elements = [
        _encode_dicom_vr(0x0002, 0x0000, 'UL', struct.pack('<I', 160)),
        _encode_dicom_vr(0x0002, 0x0001, 'OB', b'\x00\x01'),
        _encode_dicom_vr(0x0002, 0x0002, 'UI', _str_to_dicom("1.2.840.10008.5.1.4.1.1.7")),
        _encode_dicom_vr(0x0002, 0x0003, 'UI', _str_to_dicom(sop_instance_uid)),
        _encode_dicom_vr(0x0002, 0x0010, 'UI', _str_to_dicom("1.2.840.10008.1.2.1")),
        _encode_dicom_vr(0x0002, 0x0012, 'UI', _str_to_dicom("1.2.826.0.1.3680043.2.135")),
        _encode_dicom_vr(0x0002, 0x0013, 'SH', _str_to_dicom("MIT-Monitor v1.0")),
    ]
    meta_group_length = sum(len(e) for e in meta_elements[1:])
    meta_elements[0] = _encode_dicom_vr(0x0002, 0x0000, 'UL', struct.pack('<I', meta_group_length))
    meta_bytes = b''.join(meta_elements)

    patient_name = patient_info.get("PatientName", "Anonymous^Patient")
    patient_id = patient_info.get("PatientID", "MIT-000001")
    patient_birthdate = patient_info.get("PatientBirthDate", "")
    patient_sex = patient_info.get("PatientSex", "O")
    study_desc = study_info.get("StudyDescription", "MIT Brain Edema Monitoring")
    study_id = study_info.get("StudyID", "STUDY-001")
    series_desc = series_info.get("SeriesDescription", "Conductivity Map")
    series_num = series_info.get("SeriesNumber", "1")
    instance_num = series_info.get("InstanceNumber", "1")

    patient_elements = [
        _encode_dicom_vr(0x0010, 0x0010, 'PN', _str_to_dicom(patient_name)),
        _encode_dicom_vr(0x0010, 0x0020, 'LO', _str_to_dicom(patient_id)),
        _encode_dicom_vr(0x0010, 0x0030, 'DA', _str_to_dicom(patient_birthdate)),
        _encode_dicom_vr(0x0010, 0x0040, 'CS', _str_to_dicom(patient_sex)),
    ]

    study_elements = [
        _encode_dicom_vr(0x0020, 0x000D, 'UI', _str_to_dicom(study_instance_uid)),
        _encode_dicom_vr(0x0020, 0x0010, 'SH', _str_to_dicom(study_id)),
        _encode_dicom_vr(0x0008, 0x0020, 'DA', _str_to_dicom(date_str)),
        _encode_dicom_vr(0x0008, 0x0030, 'TM', _str_to_dicom(time_str)),
        _encode_dicom_vr(0x0008, 0x0050, 'SH', _str_to_dicom("")),
        _encode_dicom_vr(0x0008, 0x0090, 'PN', _str_to_dicom("^MIT^System")),
        _encode_dicom_vr(0x0008, 0x1030, 'LO', _str_to_dicom(study_desc)),
    ]

    series_elements = [
        _encode_dicom_vr(0x0020, 0x000E, 'UI', _str_to_dicom(series_instance_uid)),
        _encode_dicom_vr(0x0020, 0x0011, 'IS', _str_to_dicom(series_num)),
        _encode_dicom_vr(0x0008, 0x0060, 'CS', _str_to_dicom(modality)),
        _encode_dicom_vr(0x0008, 0x0021, 'DA', _str_to_dicom(date_str)),
        _encode_dicom_vr(0x0008, 0x0031, 'TM', _str_to_dicom(time_str)),
        _encode_dicom_vr(0x0008, 0x103E, 'LO', _str_to_dicom(series_desc)),
        _encode_dicom_vr(0x0054, 0x0010, 'SH', _str_to_dicom("MIT")),
    ]

    equipment_elements = [
        _encode_dicom_vr(0x0008, 0x0070, 'LO', _str_to_dicom("MIT Research Group")),
        _encode_dicom_vr(0x0008, 0x0080, 'LO', _str_to_dicom("MIT Brain Monitor Lab")),
        _encode_dicom_vr(0x0008, 0x0081, 'ST', _str_to_dicom("Research Facility")),
        _encode_dicom_vr(0x0008, 0x0090, 'PN', _str_to_dicom("^MIT^System")),
        _encode_dicom_vr(0x0018, 0x1000, 'LO', _str_to_dicom("MIT-MONITOR-V1")),
        _encode_dicom_vr(0x0018, 0x1020, 'LO', _str_to_dicom("MIT-SW-1.0")),
    ]

    general_img_elements = [
        _encode_dicom_vr(0x0008, 0x0008, 'CS',
                         _str_to_dicom("ORIGINAL\\PRIMARY\\OTHER")),
        _encode_dicom_vr(0x0008, 0x0016, 'UI', _str_to_dicom("1.2.840.10008.5.1.4.1.1.7")),
        _encode_dicom_vr(0x0008, 0x0018, 'UI', _str_to_dicom(sop_instance_uid)),
        _encode_dicom_vr(0x0008, 0x0019, 'UI', _str_to_dicom("1.2.840.10008.5.1.4.1.1.7")),
        _encode_dicom_vr(0x0020, 0x0013, 'IS', _str_to_dicom(instance_num)),
        _encode_dicom_vr(0x0020, 0x0052, 'UI', _str_to_dicom(frame_of_ref_uid)),
        _encode_dicom_vr(0x0028, 0x0002, 'US', struct.pack('<H', 1)),
        _encode_dicom_vr(0x0028, 0x0004, 'CS', _str_to_dicom("MONOCHROME2")),
        _encode_dicom_vr(0x0028, 0x0006, 'US', struct.pack('<H', 0)),
        _encode_dicom_vr(0x0028, 0x0008, 'IS', _str_to_dicom("1")),
        _encode_dicom_vr(0x0028, 0x0009, 'AT', struct.pack('<HH', 0x0028, 0x0010)),
        _encode_dicom_vr(0x0028, 0x0010, 'US', struct.pack('<H', rows)),
        _encode_dicom_vr(0x0028, 0x0011, 'US', struct.pack('<H', cols)),
        _encode_dicom_vr(0x0028, 0x0030, 'DS', _str_to_dicom("5.0\\5.0")),
        _encode_dicom_vr(0x0028, 0x0100, 'US', struct.pack('<H', 16)),
        _encode_dicom_vr(0x0028, 0x0101, 'US', struct.pack('<H', 16)),
        _encode_dicom_vr(0x0028, 0x0102, 'US', struct.pack('<H', 15)),
        _encode_dicom_vr(0x0028, 0x0103, 'US', struct.pack('<H', 0)),
        _encode_dicom_vr(0x0028, 0x0106, 'US', struct.pack('<H', 0)),
        _encode_dicom_vr(0x0028, 0x0107, 'US', struct.pack('<H', 65535)),
        _encode_dicom_vr(0x0028, 0x1050, 'DS', _str_to_dicom(str(window_center))),
        _encode_dicom_vr(0x0028, 0x1051, 'DS', _str_to_dicom(str(window_width))),
        _encode_dicom_vr(0x0028, 0x1052, 'DS', _str_to_dicom(str(rescale_intercept))),
        _encode_dicom_vr(0x0028, 0x1053, 'DS', _str_to_dicom(str(rescale_slope))),
        _encode_dicom_vr(0x0028, 0x1054, 'LO', _str_to_dicom("S/m")),
        _encode_dicom_vr(0x0028, 0x1055, 'LO', _str_to_dicom("Conductivity")),
    ]

    private_elements = [
        _encode_dicom_vr(0x7FE1, 0x0010, 'LO', _str_to_dicom("MIT MONITOR PRIVATE")),
        _encode_dicom_vr(0x7FE1, 0x0011, 'DS', _str_to_dicom(str(float(np.min(matrix))))),
        _encode_dicom_vr(0x7FE1, 0x0012, 'DS', _str_to_dicom(str(float(np.max(matrix))))),
        _encode_dicom_vr(0x7FE1, 0x0013, 'DS', _str_to_dicom(str(float(np.mean(matrix))))),
        _encode_dicom_vr(0x7FE1, 0x0014, 'IS', _str_to_dicom(str(rows))),
        _encode_dicom_vr(0x7FE1, 0x0015, 'IS', _str_to_dicom(str(cols))),
    ]

    pixel_element = _encode_dicom_vr(0x7FE0, 0x0010, 'OW', pixel_data)

    preamble = b'\x00' * 128
    magic = b'DICM'

    dataset_bytes = b''.join(
        patient_elements +
        study_elements +
        series_elements +
        equipment_elements +
        general_img_elements +
        private_elements +
        [pixel_element]
    )

    return preamble + magic + meta_bytes + dataset_bytes


def export_simulation_to_dicom(
    simulation_result: Dict[str, Any],
    export_type: str = "reconstructed",
    frequency: Optional[str] = None
) -> Dict[str, Any]:
    if export_type == "true":
        matrix = np.array(simulation_result.get("true_conductivity"))
    elif export_type == "multifreq" and frequency:
        reconstructions = simulation_result.get("reconstructions", {})
        matrix = np.array(reconstructions.get(frequency, simulation_result.get("reconstructed_conductivity")))
    elif export_type == "fused":
        matrix = np.array(simulation_result.get("fused_reconstruction", simulation_result.get("reconstructed_conductivity")))
    else:
        matrix = np.array(simulation_result.get("reconstructed_conductivity"))

    patient_info = simulation_result.get("patient_info", {})
    study_info = {
        "StudyDescription": f"MIT Brain Edema Study - {export_type.upper()}",
        "StudyID": simulation_result.get("task_id", "STUDY-001")[:16]
    }
    series_info = {
        "SeriesDescription": f"Conductivity Map - {export_type}" + (f" @ {frequency}" if frequency else ""),
        "SeriesNumber": "1",
        "InstanceNumber": "1"
    }

    dicom_bytes = matrix_to_dicom(
        matrix,
        patient_info=patient_info,
        study_info=study_info,
        series_info=series_info
    )

    b64 = base64.b64encode(dicom_bytes).decode('ascii')
    filename = f"MIT_{export_type}" + (f"_{frequency.replace('/', '')}" if frequency else "") + f"_{simulation_result.get('task_id', 'unknown')}.dcm"

    return {
        "filename": filename,
        "dicom_bytes_base64": b64,
        "content_type": "application/dicom",
        "matrix_shape": list(matrix.shape),
        "matrix_min": float(np.min(matrix)),
        "matrix_max": float(np.max(matrix)),
        "matrix_mean": float(np.mean(matrix))
    }


def export_multifreq_to_dicom(simulation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    exports = []
    for freq in ["1kHz", "10kHz", "100kHz"]:
        exp = export_simulation_to_dicom(simulation_result, export_type="multifreq", frequency=freq)
        exports.append(exp)
    if "fused_reconstruction" in simulation_result:
        fused = export_simulation_to_dicom(simulation_result, export_type="fused")
        exports.append(fused)
    return exports
