import streamlit as st
import csv
import io
from site_kml_gen import generate_kml_for_points

st.set_page_config(page_title="CSV → KML Generator", layout="centered")
st.title("CSV → KML Generator (Sites → KML)")

# CSV template
csv_template = """SiteName,Latitude,Longitude,Icon,IconScale,Description,FolderName,SecondFolderName,ThirdFolderName
Site A,10.762622,106.660172,https://maps.google.com/mapfiles/kml/paddle/red-circle.png,1.0,Example site A,Region 1,District A,
Site B,10.780000,106.700000,https://maps.google.com/mapfiles/kml/paddle/blu-circle.png,1.0,Example site B,Region 1,District B,
"""

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("Upload a CSV file following the template or paste CSV content.")
with col2:
    st.download_button(
        "Download CSV template",
        data=csv_template,
        file_name="sites_template.csv",
        mime="text/csv",
        key="download_template_v1",
    )

uploaded = st.file_uploader("Upload CSV file", type=["csv"], key="upload_csv_v1")
pasted = st.text_area(
    "Or paste CSV here (optional)",
    height=160,
    placeholder="Paste CSV content matching template headers...",
    key="paste_csv_v1",
)

output_name = st.text_input("Output KML file name", value="sites_output.kml", key="output_name_v1")
doc_name = st.text_input("KML Document name", value="Sites from CSV", key="doc_name_v1")

def parse_csv_to_items(csv_text):
    buf = io.StringIO(csv_text)
    reader = csv.DictReader(buf)
    items = []
    for row in reader:
        # Normalize keys to expected names and keep values as strings;
        # generate_kml_for_points will convert lat/lon/iconscale as needed.
        item = {
            "SiteName": (row.get("SiteName") or "").strip(),
            "Latitude": (row.get("Latitude") or "").strip(),
            "Longitude": (row.get("Longitude") or "").strip(),
            "Icon": (row.get("Icon") or "").strip(),
            "IconScale": (row.get("IconScale") or "").strip() or "1.0",
            "Description": (row.get("Description") or "").strip(),
            "FolderName": (row.get("FolderName") or "").strip(),
            "SecondFolderName": (row.get("SecondFolderName") or "").strip(),
            "ThirdFolderName": (row.get("ThirdFolderName") or "").strip(),
        }
        # Skip rows missing lat/lon
        if item["Latitude"] == "" or item["Longitude"] == "":
            continue
        items.append(item)
    return items

if st.button("Generate KML", key="generate_button_v1"):
    csv_text = None
    if uploaded is not None:
        try:
            csv_text = uploaded.getvalue().decode('utf-8')
        except Exception as e:
            st.error(f"Cannot read uploaded file: {e}", key="error_read_upload_v1")
            st.stop()
    elif pasted.strip():
        csv_text = pasted
    else:
        st.error("Provide CSV via upload or paste.", key="error_no_input_v1")
        st.stop()

    items = parse_csv_to_items(csv_text)
    if not items:
        st.error("No valid rows with Latitude and Longitude found in CSV.", key="error_no_rows_v1")
        st.stop()

    st.info(f"Parsed {len(items)} valid rows. Generating KML...")
    try:
        kml_content = generate_kml_for_points(items, doc_name=doc_name)
    except Exception as e:
        st.error(f"Error generating KML: {e}", key="error_generate_v1")
        st.stop()

    if not kml_content:
        st.error("KML generation returned no content.", key="error_empty_kml_v1")
        st.stop()

    st.success("KML generated.")
    st.download_button(
        "Download KML",
        data=kml_content,
        file_name=output_name,
        mime="application/vnd.google-earth.kml+xml",
        key="download_kml_v1",
    )
    with st.expander("Preview KML", expanded=False):
        st.code(kml_content, language="xml")
    with st.expander("First 20 parsed rows", expanded=False):
        st.table(items[:20])