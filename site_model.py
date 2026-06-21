"""
site_model.py — DFR Site Survey data model.

All dataclasses use to_json() / from_json() with uppercase FIELD_ID keys for
stable serialization across report templates and API consumers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, List


VALID_PHOTO_CATEGORIES = ["Site", "Installation", "Infrastructure", "RF", "Access"]


# ---------------------------------------------------------------------------
# SurveyPhoto
# ---------------------------------------------------------------------------

@dataclass
class SurveyPhoto:
    """One GPS-tagged photo captured during a site survey."""

    photo_id: str
    file_path: str
    category: str

    # EXIF / camera metadata
    photo_date: Optional[str] = None
    photo_time: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    photo_heading: Optional[float] = None
    photo_altitude: Optional[float] = None

    # Internal / UI fields
    annotations: List[str] = field(default_factory=list)
    selected_for_report: bool = False

    def to_json(self) -> dict:
        return {
            "PHOTO_ID": self.photo_id,
            "file_path": self.file_path,
            "category": self.category,
            "PHOTO_DATE": self.photo_date,
            "PHOTO_TIME": self.photo_time,
            "GPS_LATITUDE": self.gps_latitude,
            "GPS_LONGITUDE": self.gps_longitude,
            "PHOTO_HEADING": self.photo_heading,
            "PHOTO_ALTITUDE": self.photo_altitude,
            "annotations": list(self.annotations),
            "selected_for_report": self.selected_for_report,
        }

    @classmethod
    def from_json(cls, data: dict) -> SurveyPhoto:
        return cls(
            photo_id=data["PHOTO_ID"],
            file_path=data["file_path"],
            category=data["category"],
            photo_date=data.get("PHOTO_DATE"),
            photo_time=data.get("PHOTO_TIME"),
            gps_latitude=data.get("GPS_LATITUDE"),
            gps_longitude=data.get("GPS_LONGITUDE"),
            photo_heading=data.get("PHOTO_HEADING"),
            photo_altitude=data.get("PHOTO_ALTITUDE"),
            annotations=list(data.get("annotations") or []),
            selected_for_report=data.get("selected_for_report", False),
        )


# ---------------------------------------------------------------------------
# SiteIdentity
# ---------------------------------------------------------------------------

@dataclass
class SiteIdentity:
    """Core identifying information for a deployment site."""

    site_name: str
    site_id: str
    agency_name: str
    site_address: str
    site_latitude: float
    site_longitude: float

    site_elevation: Optional[float] = None
    county: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    jurisdiction: Optional[str] = None
    survey_date: Optional[str] = None
    surveyor: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "SITE_NAME": self.site_name,
            "SITE_ID": self.site_id,
            "AGENCY_NAME": self.agency_name,
            "SITE_ADDRESS": self.site_address,
            "SITE_LATITUDE": self.site_latitude,
            "SITE_LONGITUDE": self.site_longitude,
            "SITE_ELEVATION": self.site_elevation,
            "COUNTY_NAME": self.county,
            "STATE_NAME": self.state,
            "ZIP_CODE": self.zip_code,
            "JURISDICTION": self.jurisdiction,
            "SURVEY_DATE": self.survey_date,
            "SURVEYOR": self.surveyor,
        }

    @classmethod
    def from_json(cls, data: dict) -> SiteIdentity:
        return cls(
            site_name=data["SITE_NAME"],
            site_id=data["SITE_ID"],
            agency_name=data["AGENCY_NAME"],
            site_address=data["SITE_ADDRESS"],
            site_latitude=data["SITE_LATITUDE"],
            site_longitude=data["SITE_LONGITUDE"],
            site_elevation=data.get("SITE_ELEVATION"),
            county=data.get("COUNTY_NAME"),
            state=data.get("STATE_NAME"),
            zip_code=data.get("ZIP_CODE"),
            jurisdiction=data.get("JURISDICTION"),
            survey_date=data.get("SURVEY_DATE"),
            surveyor=data.get("SURVEYOR"),
        )


# ---------------------------------------------------------------------------
# InstallInfo
# ---------------------------------------------------------------------------

@dataclass
class InstallInfo:
    """Dock/installation type details."""

    install_type: Optional[str] = None
    dock_type: Optional[str] = None
    future_expansion: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "INSTALL_TYPE": self.install_type,
            "DOCK_TYPE": self.dock_type,
            "FUTURE_EXPANSION": self.future_expansion,
        }

    @classmethod
    def from_json(cls, data: dict) -> InstallInfo:
        return cls(
            install_type=data.get("INSTALL_TYPE"),
            dock_type=data.get("DOCK_TYPE"),
            future_expansion=data.get("FUTURE_EXPANSION"),
        )


# ---------------------------------------------------------------------------
# AccessInfo
# ---------------------------------------------------------------------------

@dataclass
class AccessInfo:
    """Site access logistics."""

    access_type: Optional[str] = None
    roof_access: Optional[str] = None
    escort_required: Optional[bool] = None
    key_required: Optional[bool] = None
    after_hours_access: Optional[bool] = None
    parking_available: Optional[bool] = None

    def to_json(self) -> dict:
        return {
            "ACCESS_TYPE": self.access_type,
            "ROOF_ACCESS": self.roof_access,
            "ESCORT_REQUIRED": self.escort_required,
            "KEY_REQUIRED": self.key_required,
            "AFTER_HOURS_ACCESS": self.after_hours_access,
            "PARKING_AVAILABLE": self.parking_available,
        }

    @classmethod
    def from_json(cls, data: dict) -> AccessInfo:
        return cls(
            access_type=data.get("ACCESS_TYPE"),
            roof_access=data.get("ROOF_ACCESS"),
            escort_required=data.get("ESCORT_REQUIRED"),
            key_required=data.get("KEY_REQUIRED"),
            after_hours_access=data.get("AFTER_HOURS_ACCESS"),
            parking_available=data.get("PARKING_AVAILABLE"),
        )


# ---------------------------------------------------------------------------
# StructuralInfo
# ---------------------------------------------------------------------------

@dataclass
class StructuralInfo:
    """Roof and building structural details."""

    building_height: Optional[float] = None
    roof_type: Optional[str] = None
    parapet_height: Optional[float] = None
    roof_condition: Optional[str] = None
    structural_concerns: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "BUILDING_HEIGHT": self.building_height,
            "ROOF_TYPE": self.roof_type,
            "PARAPET_HEIGHT": self.parapet_height,
            "ROOF_CONDITION": self.roof_condition,
            "STRUCTURAL_CONCERNS": self.structural_concerns,
        }

    @classmethod
    def from_json(cls, data: dict) -> StructuralInfo:
        return cls(
            building_height=data.get("BUILDING_HEIGHT"),
            roof_type=data.get("ROOF_TYPE"),
            parapet_height=data.get("PARAPET_HEIGHT"),
            roof_condition=data.get("ROOF_CONDITION"),
            structural_concerns=data.get("STRUCTURAL_CONCERNS"),
        )


# ---------------------------------------------------------------------------
# DockLocation
# ---------------------------------------------------------------------------

@dataclass
class DockLocation:
    """Precise dock placement coordinates and distances."""

    dock_latitude: Optional[float] = None
    dock_longitude: Optional[float] = None
    dock_elevation: Optional[float] = None
    distance_to_edge: Optional[float] = None
    distance_to_power: Optional[float] = None
    distance_to_network: Optional[float] = None
    distance_to_antenna: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "DOCK_LATITUDE": self.dock_latitude,
            "DOCK_LONGITUDE": self.dock_longitude,
            "DOCK_ELEVATION": self.dock_elevation,
            "DISTANCE_TO_EDGE": self.distance_to_edge,
            "DISTANCE_TO_POWER": self.distance_to_power,
            "DISTANCE_TO_NETWORK": self.distance_to_network,
            "DISTANCE_TO_ANTENNA": self.distance_to_antenna,
        }

    @classmethod
    def from_json(cls, data: dict) -> DockLocation:
        return cls(
            dock_latitude=data.get("DOCK_LATITUDE"),
            dock_longitude=data.get("DOCK_LONGITUDE"),
            dock_elevation=data.get("DOCK_ELEVATION"),
            distance_to_edge=data.get("DISTANCE_TO_EDGE"),
            distance_to_power=data.get("DISTANCE_TO_POWER"),
            distance_to_network=data.get("DISTANCE_TO_NETWORK"),
            distance_to_antenna=data.get("DISTANCE_TO_ANTENNA"),
        )


# ---------------------------------------------------------------------------
# ElectricalInfo
# ---------------------------------------------------------------------------

@dataclass
class ElectricalInfo:
    """Electrical infrastructure details."""

    power_available: Optional[bool] = None
    voltage_available: Optional[str] = None
    breaker_available: Optional[bool] = None
    dedicated_circuit: Optional[bool] = None
    panel_location: Optional[str] = None
    distance_to_power: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "POWER_AVAILABLE": self.power_available,
            "VOLTAGE_AVAILABLE": self.voltage_available,
            "BREAKER_AVAILABLE": self.breaker_available,
            "DEDICATED_CIRCUIT": self.dedicated_circuit,
            "PANEL_LOCATION": self.panel_location,
            "DISTANCE_TO_POWER": self.distance_to_power,
        }

    @classmethod
    def from_json(cls, data: dict) -> ElectricalInfo:
        return cls(
            power_available=data.get("POWER_AVAILABLE"),
            voltage_available=data.get("VOLTAGE_AVAILABLE"),
            breaker_available=data.get("BREAKER_AVAILABLE"),
            dedicated_circuit=data.get("DEDICATED_CIRCUIT"),
            panel_location=data.get("PANEL_LOCATION"),
            distance_to_power=data.get("DISTANCE_TO_POWER"),
        )


# ---------------------------------------------------------------------------
# NetworkInfo
# ---------------------------------------------------------------------------

@dataclass
class NetworkInfo:
    """Network/ISP infrastructure details."""

    isp_provider: Optional[str] = None
    connection_type: Optional[str] = None
    upload_speed: Optional[str] = None
    download_speed: Optional[str] = None
    static_ip_available: Optional[bool] = None
    switch_location: Optional[str] = None
    patch_panel_location: Optional[str] = None
    distance_to_network: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "ISP_PROVIDER": self.isp_provider,
            "CONNECTION_TYPE": self.connection_type,
            "UPLOAD_SPEED": self.upload_speed,
            "DOWNLOAD_SPEED": self.download_speed,
            "STATIC_IP_AVAILABLE": self.static_ip_available,
            "SWITCH_LOCATION": self.switch_location,
            "PATCH_PANEL_LOCATION": self.patch_panel_location,
            "DISTANCE_TO_NETWORK": self.distance_to_network,
        }

    @classmethod
    def from_json(cls, data: dict) -> NetworkInfo:
        return cls(
            isp_provider=data.get("ISP_PROVIDER"),
            connection_type=data.get("CONNECTION_TYPE"),
            upload_speed=data.get("UPLOAD_SPEED"),
            download_speed=data.get("DOWNLOAD_SPEED"),
            static_ip_available=data.get("STATIC_IP_AVAILABLE"),
            switch_location=data.get("SWITCH_LOCATION"),
            patch_panel_location=data.get("PATCH_PANEL_LOCATION"),
            distance_to_network=data.get("DISTANCE_TO_NETWORK"),
        )


# ---------------------------------------------------------------------------
# RFInfo
# ---------------------------------------------------------------------------

@dataclass
class RFInfo:
    """RF / antenna line-of-sight details."""

    antenna_latitude: Optional[float] = None
    antenna_longitude: Optional[float] = None
    antenna_elevation: Optional[float] = None
    line_of_sight_status: Optional[str] = None
    obstruction_trees: Optional[bool] = None
    obstruction_buildings: Optional[bool] = None
    obstruction_water_towers: Optional[bool] = None
    obstruction_cell_towers: Optional[bool] = None
    coverage_direction: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "ANTENNA_LATITUDE": self.antenna_latitude,
            "ANTENNA_LONGITUDE": self.antenna_longitude,
            "ANTENNA_ELEVATION": self.antenna_elevation,
            "LINE_OF_SIGHT_STATUS": self.line_of_sight_status,
            "OBSTRUCTION_TREES": self.obstruction_trees,
            "OBSTRUCTION_BUILDINGS": self.obstruction_buildings,
            "OBSTRUCTION_WATER_TOWERS": self.obstruction_water_towers,
            "OBSTRUCTION_CELL_TOWERS": self.obstruction_cell_towers,
            "COVERAGE_DIRECTION": self.coverage_direction,
        }

    @classmethod
    def from_json(cls, data: dict) -> RFInfo:
        return cls(
            antenna_latitude=data.get("ANTENNA_LATITUDE"),
            antenna_longitude=data.get("ANTENNA_LONGITUDE"),
            antenna_elevation=data.get("ANTENNA_ELEVATION"),
            line_of_sight_status=data.get("LINE_OF_SIGHT_STATUS"),
            obstruction_trees=data.get("OBSTRUCTION_TREES"),
            obstruction_buildings=data.get("OBSTRUCTION_BUILDINGS"),
            obstruction_water_towers=data.get("OBSTRUCTION_WATER_TOWERS"),
            obstruction_cell_towers=data.get("OBSTRUCTION_CELL_TOWERS"),
            coverage_direction=data.get("COVERAGE_DIRECTION"),
        )


# ---------------------------------------------------------------------------
# FlightOps
# ---------------------------------------------------------------------------

@dataclass
class FlightOps:
    """Flight operations and airspace context."""

    primary_response_area: Optional[str] = None
    launch_direction: Optional[str] = None
    emergency_landing_zone: Optional[str] = None
    nearby_airports: Optional[str] = None
    nearby_heliports: Optional[str] = None
    airspace_class: Optional[str] = None
    flight_restrictions: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "PRIMARY_RESPONSE_AREA": self.primary_response_area,
            "LAUNCH_DIRECTION": self.launch_direction,
            "EMERGENCY_LANDING_ZONE": self.emergency_landing_zone,
            "NEARBY_AIRPORTS": self.nearby_airports,
            "NEARBY_HELIPORTS": self.nearby_heliports,
            "AIRSPACE_CLASS": self.airspace_class,
            "FLIGHT_RESTRICTIONS": self.flight_restrictions,
        }

    @classmethod
    def from_json(cls, data: dict) -> FlightOps:
        return cls(
            primary_response_area=data.get("PRIMARY_RESPONSE_AREA"),
            launch_direction=data.get("LAUNCH_DIRECTION"),
            emergency_landing_zone=data.get("EMERGENCY_LANDING_ZONE"),
            nearby_airports=data.get("NEARBY_AIRPORTS"),
            nearby_heliports=data.get("NEARBY_HELIPORTS"),
            airspace_class=data.get("AIRSPACE_CLASS"),
            flight_restrictions=data.get("FLIGHT_RESTRICTIONS"),
        )


# ---------------------------------------------------------------------------
# SiteScores
# ---------------------------------------------------------------------------

@dataclass
class SiteScores:
    """Placeholder scoring model — populated by future scoring engine."""

    installation_score: Optional[float] = None
    engineering_score: Optional[float] = None
    rf_score: Optional[float] = None
    safety_score: Optional[float] = None
    overall_score: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "INSTALLATION_SCORE": self.installation_score,
            "ENGINEERING_SCORE": self.engineering_score,
            "RF_SCORE": self.rf_score,
            "SAFETY_SCORE": self.safety_score,
            "OVERALL_SCORE": self.overall_score,
        }

    @classmethod
    def from_json(cls, data: dict) -> SiteScores:
        return cls(
            installation_score=data.get("INSTALLATION_SCORE"),
            engineering_score=data.get("ENGINEERING_SCORE"),
            rf_score=data.get("RF_SCORE"),
            safety_score=data.get("SAFETY_SCORE"),
            overall_score=data.get("OVERALL_SCORE"),
        )


# ---------------------------------------------------------------------------
# Photo categorization helpers
# ---------------------------------------------------------------------------

PHOTO_CATEGORY_KEYWORDS = {
    "Site": ["front", "rear", "overview", "building", "panorama", "360"],
    "Installation": ["dock", "proposed", "north_view", "south_view", "east_view", "west_view"],
    "Infrastructure": ["panel", "breaker", "network", "closet", "switch", "demarc"],
    "RF": ["antenna", "rf", "radio", "transmit"],
    "Access": ["hatch", "ladder", "stair", "elevator", "gate", "access"],
}


def categorize_photo_by_filename(filename: str) -> str:
    lower = filename.lower()
    for category, keywords in PHOTO_CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "Site"


# ---------------------------------------------------------------------------
# CandidateSite
# ---------------------------------------------------------------------------

@dataclass
class CandidateSite:
    """Top-level model representing one candidate DFR deployment site."""

    identity: SiteIdentity
    installation: InstallInfo = field(default_factory=InstallInfo)
    access: AccessInfo = field(default_factory=AccessInfo)
    structure: StructuralInfo = field(default_factory=StructuralInfo)
    dock: DockLocation = field(default_factory=DockLocation)
    electrical: ElectricalInfo = field(default_factory=ElectricalInfo)
    network: NetworkInfo = field(default_factory=NetworkInfo)
    rf: RFInfo = field(default_factory=RFInfo)
    flight: FlightOps = field(default_factory=FlightOps)
    scores: SiteScores = field(default_factory=SiteScores)
    photos: List[SurveyPhoto] = field(default_factory=list)
    checklist_provenance: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "identity": self.identity.to_json(),
            "installation": self.installation.to_json(),
            "access": self.access.to_json(),
            "structure": self.structure.to_json(),
            "dock": self.dock.to_json(),
            "electrical": self.electrical.to_json(),
            "network": self.network.to_json(),
            "rf": self.rf.to_json(),
            "flight": self.flight.to_json(),
            "scores": self.scores.to_json(),
            "photos": [p.to_json() for p in self.photos],
            "checklist_provenance": dict(self.checklist_provenance),
        }

    @classmethod
    def from_json(cls, data: dict) -> CandidateSite:
        return cls(
            identity=SiteIdentity.from_json(data["identity"]),
            installation=InstallInfo.from_json(data.get("installation") or {}),
            access=AccessInfo.from_json(data.get("access") or {}),
            structure=StructuralInfo.from_json(data.get("structure") or {}),
            dock=DockLocation.from_json(data.get("dock") or {}),
            electrical=ElectricalInfo.from_json(data.get("electrical") or {}),
            network=NetworkInfo.from_json(data.get("network") or {}),
            rf=RFInfo.from_json(data.get("rf") or {}),
            flight=FlightOps.from_json(data.get("flight") or {}),
            scores=SiteScores.from_json(data.get("scores") or {}),
            photos=[SurveyPhoto.from_json(p) for p in (data.get("photos") or [])],
            checklist_provenance=dict(data.get("checklist_provenance") or {}),
        )

    @classmethod
    def from_site_dict(cls, data: dict) -> CandidateSite:
        """Convert a legacy processor.py site dict to a CandidateSite."""
        site_name = data.get("city") or data.get("address") or ""
        identity = SiteIdentity(
            site_name=site_name,
            site_id=data.get("site_id", ""),
            agency_name=data.get("agency_name", ""),
            site_address=data.get("address", ""),
            site_latitude=data.get("latitude", 0.0),
            site_longitude=data.get("longitude", 0.0),
        )

        photos: List[SurveyPhoto] = []
        for idx, img in enumerate(data.get("images") or []):
            file_path = img.get("dest_path") or img.get("path", "")
            filename = img.get("filename") or os.path.basename(file_path)
            category = categorize_photo_by_filename(filename)
            raw_time = img.get("time", "")
            photo_date: Optional[str] = None
            photo_time: Optional[str] = None
            if raw_time:
                parts = str(raw_time).split(" ", 1)
                photo_date = parts[0] if parts else None
                photo_time = parts[1] if len(parts) > 1 else None
            photos.append(SurveyPhoto(
                photo_id=f"IMG_{idx + 1:03d}",
                file_path=file_path,
                category=category,
                photo_date=photo_date,
                photo_time=photo_time,
                gps_latitude=img.get("lat"),
                gps_longitude=img.get("lon"),
            ))

        site = cls(identity=identity, photos=photos)

        # Carry forward analysis dict fields
        analysis = data.get("analysis") or {}
        if analysis.get("roof_access"):
            site.access.roof_access = analysis["roof_access"]
        if analysis.get("roof_type"):
            site.structure.roof_type = analysis["roof_type"]

        # Carry forward airspace dict
        airspace = data.get("airspace") or {}
        if airspace.get("designator"):
            site.flight.airspace_class = airspace["designator"]

        # Carry forward airfield_info dict
        airfield_info = data.get("airfield_info") or {}
        if airfield_info.get("name"):
            site.flight.nearby_airports = airfield_info["name"]

        return site

    def to_csv_row(self) -> dict:
        """Flatten all sub-models into a single dict suitable for CSV export."""
        row: dict = {}
        row.update(self.identity.to_json())
        row.update(self.installation.to_json())
        row.update(self.access.to_json())
        row.update(self.structure.to_json())
        row.update(self.dock.to_json())
        row.update(self.electrical.to_json())
        row.update(self.network.to_json())
        row.update(self.rf.to_json())
        row.update(self.flight.to_json())
        row.update(self.scores.to_json())
        return row

    def compute_scores(self) -> None:
        """Placeholder — scoring logic to be implemented by future scoring engine."""
        pass

    @staticmethod
    def rank_sites(sites: list) -> list:
        """Return sites in ranked order (placeholder — no-op sort)."""
        return list(sites)


def export_sites_json(sites: list, output_path: str) -> str:
    """Export a list of CandidateSite objects to a JSON file."""
    import json
    data = [site.to_json() for site in sites]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return output_path


def export_sites_csv(sites: list, output_path: str) -> str:
    """Export a list of CandidateSite objects to a CSV file. One row per site."""
    import csv
    if not sites:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return output_path

    rows = [site.to_csv_row() for site in sites]
    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v is not None else "" for k, v in row.items()})

    return output_path
