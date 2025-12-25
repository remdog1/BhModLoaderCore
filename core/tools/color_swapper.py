"""
Color Swapper Tool for Brawlhalla Mod Loader
Enables batch color replacement within SWF sprites and shapes
"""

import os
import re
from typing import Dict, List, Tuple, Optional
from ..swf.swf import Swf, GetElementId
from ..ffdec.classes import (
    DefineShapeTags, DefineBitsLossless2Tag, DefineSpriteTag,
    FILLSTYLE, DefineBitsLosslessTags
)
from ..notifications import NotificationType
from .basedispatch import SendNotification


class ColorSwapper:
    """Handles color swapping functionality for SWF files"""
    
    def __init__(self, swf_path: str):
        self.swf_path = swf_path
        self.swf = Swf(swf_path)
        self.color_replacements = {}
        
    def analyze_colors(self) -> Dict[int, int]:
        """
        Analyze all colors used in the SWF file
        Returns a dictionary of color values and their usage count
        """
        color_usage = {}
        
        for element in self.swf.elementsList:
            if isinstance(element, DefineShapeTags):
                # Extract colors from shape fill styles
                if hasattr(element, 'shapes') and hasattr(element.shapes, 'fillStyles'):
                    if hasattr(element.shapes.fillStyles, 'fillStyles'):
                        for fill_style in element.shapes.fillStyles.fillStyles:
                            if hasattr(fill_style, 'color') and fill_style.color:
                                color = int(fill_style.color)
                                color_usage[color] = color_usage.get(color, 0) + 1
                                
            elif isinstance(element, DefineBitsLossless2Tag):
                # Extract colors from bitmap data
                if hasattr(element, 'bitmapData'):
                    # This would require more complex bitmap analysis
                    # For now, we'll focus on shape colors
                    pass
                    
        return color_usage
    
    def swap_color(self, old_color: int, new_color: int, 
                   target_sprites: Optional[List[str]] = None) -> int:
        """
        Swap a specific color throughout the SWF
        
        Args:
            old_color: Color to replace (RGB integer)
            new_color: New color to use (RGB integer)
            target_sprites: Optional list of sprite names to limit replacement
            
        Returns:
            Number of replacements made
        """
        replacements = 0
        
        for element in self.swf.elementsList:
            if isinstance(element, DefineShapeTags):
                # Check if this sprite should be processed
                if target_sprites:
                    sprite_name = self._get_sprite_name(element)
                    if sprite_name not in target_sprites:
                        continue
                
                # Process shape fill styles
                if hasattr(element, 'shapes') and hasattr(element.shapes, 'fillStyles'):
                    if hasattr(element.shapes.fillStyles, 'fillStyles'):
                        for fill_style in element.shapes.fillStyles.fillStyles:
                            if hasattr(fill_style, 'color') and fill_style.color:
                                if int(fill_style.color) == old_color:
                                    fill_style.color = new_color
                                    element.setModified(True)
                                    replacements += 1
                                    
            elif isinstance(element, DefineSpriteTag):
                # Process nested sprites
                if hasattr(element, 'tags'):
                    for tag in element.tags:
                        if isinstance(tag, DefineShapeTags):
                            if hasattr(tag, 'shapes') and hasattr(tag.shapes, 'fillStyles'):
                                if hasattr(tag.shapes.fillStyles, 'fillStyles'):
                                    for fill_style in tag.shapes.fillStyles.fillStyles:
                                        if hasattr(fill_style, 'color') and fill_style.color:
                                            if int(fill_style.color) == old_color:
                                                fill_style.color = new_color
                                                tag.setModified(True)
                                                replacements += 1
                                                
        return replacements
    
    def batch_color_swap(self, color_mappings: Dict[int, int],
                        target_sprites: Optional[List[str]] = None) -> Dict[int, int]:
        """
        Perform multiple color swaps in one operation
        
        Args:
            color_mappings: Dictionary of old_color -> new_color mappings
            target_sprites: Optional list of sprite names to limit replacement
            
        Returns:
            Dictionary of old_color -> replacement_count
        """
        results = {}
        
        for old_color, new_color in color_mappings.items():
            count = self.swap_color(old_color, new_color, target_sprites)
            results[old_color] = count
            
        return results
    
    def _get_sprite_name(self, element) -> Optional[str]:
        """Get the sprite name for an element"""
        try:
            element_id = GetElementId(element)
            if self.swf.symbolClass:
                return self.swf.symbolClass.getTagName(element_id)
        except:
            pass
        return None
    
    def save_changes(self):
        """Save the modified SWF file"""
        self.swf.save()
        
    def close(self):
        """Close the SWF file"""
        self.swf.close()


class ColorConverter:
    """Handles color format conversions and utilities"""
    
    @staticmethod
    def rgb_to_int(r: int, g: int, b: int) -> int:
        """Convert RGB values to integer color"""
        return (r << 16) | (g << 8) | b
    
    @staticmethod
    def int_to_rgb(color_int: int) -> Tuple[int, int, int]:
        """Convert integer color to RGB values"""
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b)
    
    @staticmethod
    def hex_to_int(hex_color: str) -> int:
        """Convert hex color string to integer"""
        hex_color = hex_color.lstrip('#')
        return int(hex_color, 16)
    
    @staticmethod
    def int_to_hex(color_int: int) -> str:
        """Convert integer color to hex string"""
        return f"#{color_int:06X}"
    
    @staticmethod
    def find_similar_colors(target_color: int, color_list: List[int], 
                          tolerance: int = 30) -> List[int]:
        """
        Find colors similar to the target color within tolerance
        
        Args:
            target_color: Color to match
            color_list: List of colors to search
            tolerance: RGB difference tolerance
            
        Returns:
            List of similar colors
        """
        target_r, target_g, target_b = ColorConverter.int_to_rgb(target_color)
        similar_colors = []
        
        for color in color_list:
            r, g, b = ColorConverter.int_to_rgb(color)
            if (abs(r - target_r) <= tolerance and 
                abs(g - target_g) <= tolerance and 
                abs(b - target_b) <= tolerance):
                similar_colors.append(color)
                
        return similar_colors


def create_color_swapper_ui():
    """Create UI components for the Color Swapper tool"""
    # This would integrate with the existing UI framework
    pass


def process_swf_colors(swf_path: str, color_mappings: Dict[int, int], 
                      target_sprites: Optional[List[str]] = None) -> Dict[int, int]:
    """
    Convenience function to process SWF colors
    
    Args:
        swf_path: Path to the SWF file
        color_mappings: Dictionary of old_color -> new_color mappings
        target_sprites: Optional list of sprite names to limit replacement
        
    Returns:
        Dictionary of old_color -> replacement_count
    """
    swapper = ColorSwapper(swf_path)
    try:
        results = swapper.batch_color_swap(color_mappings, target_sprites)
        swapper.save_changes()
        return results
    finally:
        swapper.close()













