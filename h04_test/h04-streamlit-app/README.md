# h04-streamlit-app

## Overview
This project is a Streamlit application that allows users to find the nearest routes to a specified point using a KML file. The application provides a user-friendly interface for uploading KML files and entering geographic coordinates (latitude and longitude).

## Project Structure
```
h04-streamlit-app
├── src
│   ├── streamlit_app.py       # Streamlit application code
│   ├── h04.py                  # Original script for processing KML files
│   └── libs
│       └── geospatial_tools.py  # Library containing the find_nearest_routes function
├── requirements.txt            # Project dependencies
├── .gitignore                  # Files and directories to ignore by Git
└── README.md                   # Project documentation
```

## Installation
To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd h04-streamlit-app
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
To run the Streamlit application, execute the following command in your terminal:
```
streamlit run src/streamlit_app.py
```

Once the application is running, you can:

1. Upload a KML file containing route data.
2. Enter the latitude and longitude of the point you are interested in.
3. Click the "Find Nearest Routes" button to display the results.

## Contributing
Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.