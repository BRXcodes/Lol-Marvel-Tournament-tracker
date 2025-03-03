import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, List, Dict, Any

load_dotenv()

class PandaScoreAPI:
    BASE_URL = "https://api.pandascore.co"
    SUPPORTED_GAMES = {
        "lol": "league-of-legends",
        "valorant": "valorant"
    }
    
    def __init__(self):
        self.api_key = os.getenv("PANDASCORE_API_KEY")
        if not self.api_key:
            raise ValueError("PANDASCORE_API_KEY environment variable is not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
    
    def get_tournaments(self, game: Optional[str] = None, status: str = "running,upcoming", per_page: int = 50) -> List[Dict[Any, Any]]:
        """
        Fetch tournaments with enhanced game-specific data
        """
        if game and game not in self.SUPPORTED_GAMES:
            raise ValueError(f"Unsupported game. Supported games are: {', '.join(self.SUPPORTED_GAMES.keys())}")
            
        # Use game-specific endpoints for better filtering
        if game == "lol":
            endpoint = f"{self.BASE_URL}/lol/tournaments"
        elif game == "valorant":
            endpoint = f"{self.BASE_URL}/valorant/tournaments"
        else:
            endpoint = f"{self.BASE_URL}/tournaments"
            
        params = {
            "per_page": per_page,
            "status": status
        }
        
        if game and game not in ["lol", "valorant"]:  # Only add videogame param for general endpoint
            params["videogame"] = self.SUPPORTED_GAMES[game]
            
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        tournaments = response.json()
        
        # Filter tournaments to ensure they match the requested game
        filtered_tournaments = []
        for tournament in tournaments:
            videogame = tournament.get("videogame", {})
            game_slug = videogame.get("slug") if isinstance(videogame, dict) else None
            
            # Only include tournaments that match the requested game
            if game and game in self.SUPPORTED_GAMES:
                if game_slug != self.SUPPORTED_GAMES[game]:
                    continue
            
            enhanced_tournament = tournament.copy()
            
            # Add league info if available
            if "league" in tournament:
                enhanced_tournament["league_info"] = {
                    "name": tournament["league"].get("name"),
                    "image_url": tournament["league"].get("image_url"),
                    "region": tournament["league"].get("region")
                }
            
            # Add series info if available
            if "series" in tournament:
                enhanced_tournament["series_info"] = {
                    "name": tournament["series"].get("name"),
                    "season": tournament["series"].get("season")
                }
            
            # Add game-specific details
            if game == "lol":
                enhanced_tournament["game_details"] = {
                    "patch_version": tournament.get("patch_version"),
                    "tournament_type": tournament.get("tournament_type", "Unknown"),
                    "region": tournament.get("region", "International")
                }
            elif game == "valorant":
                enhanced_tournament["game_details"] = {
                    "patch": tournament.get("patch", "Unknown"),
                    "series_type": tournament.get("serie_type", "Unknown"),
                    "region": tournament.get("region", "International")
                }
            
            filtered_tournaments.append(enhanced_tournament)
        
        return filtered_tournaments
    
    def get_teams(self, game: Optional[str] = None, per_page: int = 50) -> List[Dict[Any, Any]]:
        """Fetch teams with enhanced statistics"""
        if game and game not in self.SUPPORTED_GAMES:
            raise ValueError(f"Unsupported game. Supported games are: {', '.join(self.SUPPORTED_GAMES.keys())}")
            
        endpoint = f"{self.BASE_URL}/teams"
        params = {
            "per_page": per_page
        }
        
        if game:
            params["videogame"] = self.SUPPORTED_GAMES[game]
            
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        teams = response.json()
        
        # Enhance team data
        enhanced_teams = []
        for team in teams:
            enhanced_team = team.copy()
            
            # Add player roster if available
            if "players" in team:
                enhanced_team["roster"] = [
                    {
                        "name": player.get("name"),
                        "role": player.get("role"),
                        "hometown": player.get("hometown"),
                        "image_url": player.get("image_url")
                    }
                    for player in team["players"]
                ]
            
            # Add recent performance
            if game == "lol":
                matches_endpoint = f"{self.BASE_URL}/teams/{team['id']}/matches"
                matches_response = requests.get(matches_endpoint, headers=self.headers, params={"per_page": 5})
                if matches_response.ok:
                    recent_matches = matches_response.json()
                    enhanced_team["recent_performance"] = {
                        "matches": recent_matches,
                        "win_rate": self._calculate_win_rate(recent_matches, team['id'])
                    }
            
            enhanced_teams.append(enhanced_team)
        
        return enhanced_teams
    
    def get_tournament(self, tournament_id: str) -> Dict[Any, Any]:
        """Fetch details for a specific tournament"""
        endpoint = f"{self.BASE_URL}/tournaments/{tournament_id}"
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        tournament = response.json()
        
        # Enhance tournament data
        enhanced_tournament = tournament.copy()
        
        # Add league info if available
        if "league" in tournament:
            enhanced_tournament["league_info"] = {
                "name": tournament["league"].get("name"),
                "image_url": tournament["league"].get("image_url"),
                "region": tournament["league"].get("region")
            }
        
        # Add series info if available
        if "series" in tournament:
            enhanced_tournament["series_info"] = {
                "name": tournament["series"].get("name"),
                "season": tournament["series"].get("season")
            }
        
        # Add game-specific details based on videogame
        videogame = tournament.get("videogame", {})
        if videogame.get("slug") == "league-of-legends":
            enhanced_tournament["game_details"] = {
                "patch_version": tournament.get("patch_version"),
                "tournament_type": tournament.get("tournament_type", "Unknown"),
                "region": tournament.get("region", "International")
            }
        elif videogame.get("slug") == "valorant":
            enhanced_tournament["game_details"] = {
                "patch": tournament.get("patch", "Unknown"),
                "series_type": tournament.get("serie_type", "Unknown"),
                "region": tournament.get("region", "International")
            }
        
        return enhanced_tournament

    def get_match(self, match_id: str) -> Dict[Any, Any]:
        """Fetch details for a specific match"""
        endpoint = f"{self.BASE_URL}/matches/{match_id}"
        response = requests.get(endpoint, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_matches(self, tournament_id: Optional[str] = None, status: str = "running,upcoming", per_page: int = 50) -> List[Dict[Any, Any]]:
        """Fetch matches with detailed statistics"""
        endpoint = f"{self.BASE_URL}/matches"
        params = {
            "per_page": per_page,
            "status": status
        }
        
        if tournament_id:
            params["tournament_id"] = tournament_id
            
        response = requests.get(endpoint, headers=self.headers, params=params)
        response.raise_for_status()
        matches = response.json()
        
        # Enhance match data
        enhanced_matches = []
        for match in matches:
            enhanced_match = match.copy()
            
            # Add team details
            if "opponents" in match:
                enhanced_match["opponents"] = [
                    {
                        "opponent": {
                            "id": opponent.get("opponent", {}).get("id"),
                            "name": opponent.get("opponent", {}).get("name"),
                            "image_url": opponent.get("opponent", {}).get("image_url"),
                            "acronym": opponent.get("opponent", {}).get("acronym")
                        }
                    }
                    for opponent in match["opponents"]
                ]
            
            enhanced_matches.append(enhanced_match)
        
        return enhanced_matches

    def _calculate_win_rate(self, matches: List[Dict[Any, Any]], team_id: int) -> float:
        """Calculate team's win rate from recent matches"""
        if not matches:
            return 0.0
            
        wins = sum(1 for match in matches 
                  if match.get("winner_id") == team_id)
        return (wins / len(matches)) * 100 