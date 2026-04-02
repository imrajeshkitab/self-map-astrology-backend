from pydantic import BaseModel, Field


class BirthRequest(BaseModel):
    year:      int   = Field(..., ge=1900, le=2100, description="Birth year")
    month:     int   = Field(..., ge=1,    le=12,   description="Birth month (1–12)")
    date:      int   = Field(..., ge=1,    le=31,   description="Birth day (1–31)")
    hours:     int   = Field(..., ge=0,    le=23,   description="Hour in 24h format")
    minutes:   int   = Field(..., ge=0,    le=59)
    seconds:   int   = Field(0,   ge=0,    le=59)
    latitude:  float = Field(..., ge=-90,  le=90,   description="Birth latitude")
    longitude: float = Field(..., ge=-180, le=180,  description="Birth longitude")
    timezone:  float = Field(..., ge=-14,  le=14,   description="UTC offset in hours (e.g. 5.5 for IST)")
    name:      str   = Field("",  max_length=120,   description="Person's name (optional)")
    place:     str   = Field("",  max_length=120,   description="Birth place label (optional)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "year": 2002, "month": 6, "date": 27,
                "hours": 2, "minutes": 0, "seconds": 0,
                "latitude": 26.8997, "longitude": 76.3324, "timezone": 5.5,
                "name": "Rajesh Kumar Meena", "place": "Dausa"
            }
        }
    }
