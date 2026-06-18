import os
import argparse
import sys
import subprocess

# Import modules
import processor
import analyzer
import reporter

def run_pipeline(source_dir, output_dir, radius_meters=90.0, report_name="Master_DFR_Site_Survey_Report.docx"):
    """
    Run the end-to-end processing pipeline from the command line.
    """
    print(f"[*] Starting Site Survey pipeline...")
    print(f"[*] Scanning source directory: {source_dir}")
    print(f"[*] Organizing and clustering into: {output_dir}")
    
    # 1. Image Ingestion and Clustering
    site_data = processor.process_and_organize_images(source_dir, output_dir, radius_meters=radius_meters)
    if not site_data:
        print("[!] No sites with valid images/GPS coordinates found.")
        return False
        
    print(f"[+] Found and clustered {len(site_data)} unique sites.")
    
    # 2. CV Analysis
    print("[*] Performing infrastructure and hardware computer vision analysis...")
    for site in site_data:
        print(f"    - Analyzing site: {site['address']}")
        site['analysis'] = analyzer.analyze_site(site)
        
        # Airspace and airfield lookup
        lat, lon = site['latitude'], site['longitude']
        site['airspace'] = reporter.query_airspace_class(lat, lon)
        airfield = reporter.query_nearest_airfield(lat, lon)
        if airfield:
            site['airfield_info'] = f"{airfield[0]} ({airfield[1]:.2f} km)"
        else:
            site['airfield_info'] = "None detected within 25 km"
            
    # 3. Report Generation
    batch_output_dir = site_data[0].get("batch_folder_path", output_dir)
    report_path = os.path.join(batch_output_dir, report_name)
    print(f"[*] Writing master Word document to: {report_path}")
    reporter.generate_word_report(site_data, report_path)
    print(f"[+] Pipeline completed successfully. Report created.")
    return True

def main():
    parser = argparse.ArgumentParser(description="DFR Site Survey & Deployment Automation Suite")
    parser.add_argument("--source", type=str, help="Path to raw image directory")
    parser.add_argument("--output", type=str, default="./processed_sites", help="Path to output directory")
    parser.add_argument("--radius", type=float, default=90.0, help="Clustering radius in meters (default 90m)")
    parser.add_argument("--report", type=str, default="Master_DFR_Site_Survey_Report.docx", help="Output report filename")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit web dashboard")
    
    args = parser.parse_args()
    
    # If explicit dashboard request or no arguments passed, launch Streamlit
    if args.dashboard or len(sys.argv) == 1:
        print("[*] Launching Streamlit web interface...")
        try:
            subprocess.run(["streamlit", "run", "dashboard.py"])
        except KeyboardInterrupt:
            print("\n[*] Dashboard stopped.")
        except FileNotFoundError:
            print("[!] Error: Streamlit not found. Please install dependencies using 'pip install -r requirements.txt'")
    else:
        if not args.source:
            print("[!] Error: Source directory is required for CLI mode. Use --source <dir> or run with --dashboard.")
            sys.exit(1)
        run_pipeline(args.source, args.output, radius_meters=args.radius, report_name=args.report)

if __name__ == "__main__":
    main()
