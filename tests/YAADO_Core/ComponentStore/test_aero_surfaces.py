import pytest
from YAADO_Core.ComponentStore.aero_surfaces import Fins, ControlSurface

def test_fins_with_nested_control_surfaces():
    """Test that Pydantic correctly parses nested control surfaces from a raw dictionary."""
    
    # This is exactly what yaml.safe_load() returns to Python behind the scenes!
    raw_data = {
        "type": "fins",
        "count": 4,
        "span": 0.5,
        "sweep": 30.0,
        "chord_root": 0.4,
        "chord_tip": 0.1,
        "control_surfaces": [
            {
                "name": "pitch_elevon",
                "function": "elevator",
                "span_fraction_start": 0.0,
                "span_fraction_end": 1.0,
                "chord_fraction": 0.25,
                "max_deflection": 15.0
            }
        ]
    }
    
    # Hand the raw dictionary to Pydantic for validation and object creation
    my_fins = Fins.model_validate(raw_data)
    
    # 1. Verify the parent fin parsed correctly
    assert my_fins.count == 4
    assert my_fins.span == 0.5
    assert Fins.UNITS["span"] == "m"
    assert Fins.UNITS["sweep"] == "deg"
    assert ControlSurface.UNITS["max_deflection"] == "deg"
    
    # 2. Verify the nested control surface list was created!
    assert len(my_fins.control_surfaces) == 1
    
    # 3. Verify Pydantic actually converted the inner dictionary into a real ControlSurface object
    elevon = my_fins.control_surfaces[0]
    assert isinstance(elevon, ControlSurface)
    assert elevon.name == "pitch_elevon"
    assert elevon.function == "elevator"
    assert elevon.chord_fraction == 0.25
    assert elevon.max_deflection == 15.0

def test_fins_without_control_surfaces():
    """Test that omitting the list defaults to an empty list safely."""
    raw_data = {
        "type": "fins",
        "count": 3,
        "span": 0.2,
        "sweep": 0.0
    }
    
    my_fins = Fins.model_validate(raw_data)
    
    # The default_factory=list kicks in and makes it safe!
    assert my_fins.control_surfaces == []
    assert len(my_fins.control_surfaces) == 0

