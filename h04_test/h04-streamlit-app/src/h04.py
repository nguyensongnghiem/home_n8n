import streamlit as st
import openpyxl
from libs.geospatial_tools import find_nearest_routes

def process_kml(kml_path, lat, lon):
    results = find_nearest_routes(kml_path, lat, lon)
    return results

def save_to_excel(results, output_excel):
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "NearestRoutes"
        ws.append(["Full Route Name", "Short Route Name", "Distance (m)", "Nearest Latitude", "Nearest Longitude"])

        for item in results:
            ws.append([
                item["full_name"],
                item["short_name"],
                item["distance_m"],
                item["nearest_lat"],
                item["nearest_lon"]
            ])

        wb.save(output_excel)
        return True
    except Exception as e:
        st.error(f"Error saving Excel file: {e}")
        return False

def main():
    st.title("Nearest Route Finder")
    
    kml_file = st.file_uploader("Upload KML file", type=["kml"])
    lat = st.number_input("Enter Latitude", format="%.6f")
    lon = st.number_input("Enter Longitude", format="%.6f")
    output_excel = st.text_input("Output Excel file path", "output.xlsx")

    if st.button("Find Nearest Routes"):
        if kml_file is not None:
            kml_path = kml_file.name
            with open(kml_path, "wb") as f:
                f.write(kml_file.getbuffer())

            results = process_kml(kml_path, lat, lon)

            if results:
                st.success(f"Found {len(results)} valid routes.")
                if st.button("Save to Excel"):
                    if save_to_excel(results, output_excel):
                        st.success(f"Excel file saved: {output_excel}")
            else:
                st.warning("No valid routes found in the KML file.")
        else:
            st.error("Please upload a KML file.")

if __name__ == "__main__":
    main()