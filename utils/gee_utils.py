"""
GEE Utility Functions for Forest Health Monitoring
Cloud masking and NDVI calculation functions for Sentinel-2 imagery
"""

import ee


def mask_s2_clouds(image):
    """
    Mask clouds in Sentinel-2 image using QA60 band.
    
    Args:
        image: ee.Image - Sentinel-2 SR image
        
    Returns:
        ee.Image - Cloud-masked image
    """
    # Get the QA60 band which contains cloud mask information
    qa = image.select('QA60')
    
    # Bits 10 and 11 are clouds and cirrus, respectively
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    
    # Both flags should be set to zero, indicating clear conditions
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
        qa.bitwiseAnd(cirrus_bit_mask).eq(0)
    )
    
    # Also mask pixels with cloud probability > 20% if SCL band available
    # Return the masked image with proper scaling
    return image.updateMask(mask).divide(10000).copyProperties(image, ['system:time_start'])


def calculate_ndvi(image):
    """
    Calculate NDVI (Normalized Difference Vegetation Index).
    
    NDVI = (NIR - Red) / (NIR + Red)
    For Sentinel-2: NIR = B8, Red = B4
    
    Args:
        image: ee.Image - Sentinel-2 image (after cloud masking/scaling)
        
    Returns:
        ee.Image - Image with NDVI band added
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)


def get_sentinel_composite(aoi, start_date, end_date):
    """
    Get cloud-masked Sentinel-2 composite for a given area and date range.
    
    Args:
        aoi: ee.Geometry - Area of interest
        start_date: str - Start date in 'YYYY-MM-DD' format
        end_date: str - End date in 'YYYY-MM-DD' format
        
    Returns:
        ee.Image - Median composite with NDVI band
    """
    # Load Sentinel-2 SR Harmonized collection
    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(aoi)
                  .filterDate(start_date, end_date)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                  .map(mask_s2_clouds))
    
    # Create median composite
    composite = collection.median().clip(aoi)
    
    # Calculate NDVI
    composite_with_ndvi = calculate_ndvi(composite)
    
    return composite_with_ndvi


def compute_mean_ndvi(ndvi_image, aoi):
    """
    Compute the mean NDVI value over a region.
    
    Args:
        ndvi_image: ee.Image - Image with NDVI band
        aoi: ee.Geometry - Area of interest
        
    Returns:
        float - Mean NDVI value
    """
    stats = ndvi_image.select('NDVI').reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=30,
        maxPixels=1e9
    )
    
    return stats.get('NDVI').getInfo()


def calculate_ndvi_timeseries(aoi, year, start_month=1, end_month=12):
    """
    Calculate monthly NDVI values for trend analysis.
    
    Args:
        aoi: ee.Geometry - Area of interest
        year: int - Year to analyze
        start_month: int - Starting month (1-12)
        end_month: int - Ending month (1-12)
        
    Returns:
        list - List of dictionaries with 'month' and 'ndvi' keys
    """
    results = []
    
    for month in range(start_month, end_month + 1):
        # Calculate days in month
        if month == 12:
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year + 1}-01-01"
        else:
            start_date = f"{year}-{month:02d}-01"
            end_date = f"{year}-{month + 1:02d}-01"
        
        try:
            # Get composite for this month
            collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                          .filterBounds(aoi)
                          .filterDate(start_date, end_date)
                          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
                          .map(mask_s2_clouds))
            
            # Check if we have images
            count = collection.size().getInfo()
            
            if count > 0:
                composite = collection.median().clip(aoi)
                composite_with_ndvi = calculate_ndvi(composite)
                mean_ndvi = compute_mean_ndvi(composite_with_ndvi, aoi)
                
                if mean_ndvi is not None:
                    results.append({
                        'month': f"{year}-{month:02d}",
                        'ndvi': round(mean_ndvi, 4)
                    })
        except Exception as e:
            # Skip months with no data
            continue
    
    return results


def get_ndvi_visualization_params():
    """
    Get visualization parameters for NDVI display.
    
    Returns:
        dict - Visualization parameters
    """
    return {
        'min': 0,
        'max': 0.8,
        'palette': ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
    }


def create_aoi_from_point(lat, lon, buffer_km=5):
    """
    Create an Area of Interest from a center point with buffer.
    
    Args:
        lat: float - Latitude
        lon: float - Longitude
        buffer_km: float - Buffer radius in kilometers
        
    Returns:
        ee.Geometry - Buffered point geometry
    """
    point = ee.Geometry.Point([lon, lat])
    # Convert km to meters for buffer
    aoi = point.buffer(buffer_km * 1000)
    return aoi
