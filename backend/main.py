from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from datetime import datetime
import logging

from database import get_db, engine
from models import Base, Tournament, Team
from services.pandascore import PandaScoreAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Esports Tournament Tracker API",
    description="API for tracking esports tournaments, teams, and matches",
    version="1.0.0"
)

# Configure CORS with more specific settings
origins = [
    "http://localhost:3000",      # Next.js development server
    "http://127.0.0.1:3000",
    "http://localhost:8000",      # FastAPI development server
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Initialize PandaScore API client
pandascore = PandaScoreAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

@app.get("/")
async def read_root():
    return {
        "message": "Welcome to the Esports Tournament Tracker API",
        "version": "1.0.0",
        "endpoints": {
            "tournaments": "/tournaments",
            "teams": "/teams",
            "predictions": "/predictions/{match_id}"
        }
    }

@app.get("/tournaments")
async def get_tournaments(
    game: Optional[str] = Query(None, description="Filter tournaments by game (e.g., lol, marvel-rivals)"),
    status: Optional[str] = Query("running,upcoming", description="Filter by tournament status"),
    db: Session = Depends(get_db)
):
    try:
        # Log the incoming request parameters
        logger.info(f"Fetching tournaments with game={game}, status={status}")
        
        if game and game not in pandascore.SUPPORTED_GAMES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported game. Supported games are: {', '.join(pandascore.SUPPORTED_GAMES.keys())}"
            )
        
        # Fetch tournaments from PandaScore
        tournaments_data = pandascore.get_tournaments(game=game, status=status)
        logger.info(f"Retrieved {len(tournaments_data)} tournaments from PandaScore")
        
        # Process each tournament
        processed_tournaments = []
        for t_data in tournaments_data:
            # Handle potential missing or null values
            begin_at = t_data.get("begin_at")
            end_at = t_data.get("end_at")
            
            # Create tournament object with processed data
            tournament_dict = {
                "external_id": str(t_data["id"]),
                "name": t_data.get("name", "Unnamed Tournament"),
                "game": t_data.get("videogame", {}).get("name", "Unknown Game"),
                "start_date": datetime.fromisoformat(begin_at.replace('Z', '+00:00')) if begin_at else None,
                "end_date": datetime.fromisoformat(end_at.replace('Z', '+00:00')) if end_at else None,
                "status": t_data.get("status", "unknown"),
                "prize_pool": t_data.get("prize_pool", "")
            }
            
            # Check if tournament already exists
            existing_tournament = db.query(Tournament).filter(
                Tournament.external_id == tournament_dict["external_id"]
            ).first()
            
            if existing_tournament:
                # Update existing tournament
                for key, value in tournament_dict.items():
                    setattr(existing_tournament, key, value)
                tournament = existing_tournament
            else:
                # Create new tournament
                tournament = Tournament(**tournament_dict)
                db.add(tournament)
            
            processed_tournaments.append(tournament)
        
        # Commit all changes at once
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Database error while saving tournaments: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save tournaments to database"
            )
        
        return {"tournaments": tournaments_data}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in get_tournaments: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tournaments: {str(e)}"
        )

@app.get("/teams")
async def get_teams(
    game: Optional[str] = Query(None, description="Filter teams by game"),
    db: Session = Depends(get_db)
):
    try:
        # Fetch teams from PandaScore
        teams_data = pandascore.get_teams(game=game)
        
        # Convert and save to database
        teams = []
        for t_data in teams_data:
            team = Team(
                external_id=str(t_data["id"]),
                name=t_data.get("name", "Unnamed Team"),
                acronym=t_data.get("acronym", ""),
                image_url=t_data.get("image_url", ""),
                game=t_data.get("current_videogame", {}).get("name", "Unknown Game")
            )
            db.merge(team)
            teams.append(team)
        
        db.commit()
        return {"teams": teams_data}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch teams: {str(e)}"
        )

@app.get("/predictions/{match_id}")
async def get_match_prediction(
    match_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Fetch match data from PandaScore
        match_data = pandascore.get_matches(match_id)
        
        if not match_data:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {match_id} not found"
            )
        
        # TODO: Implement prediction logic using historical data
        # For now, return a placeholder response
        return {
            "match_id": match_id,
            "teams": [
                match_data["opponents"][0]["opponent"]["name"],
                match_data["opponents"][1]["opponent"]["name"]
            ] if len(match_data.get("opponents", [])) >= 2 else [],
            "prediction": "pending",
            "confidence": 0.0
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get match prediction: {str(e)}"
        )

@app.get("/tournaments/{tournament_id}")
async def get_tournament_details(
    tournament_id: str,
    db: Session = Depends(get_db)
):
    try:
        # Fetch tournament details from PandaScore
        tournament_data = pandascore.get_tournament(tournament_id)
        if not tournament_data:
            raise HTTPException(
                status_code=404,
                detail=f"Tournament with ID {tournament_id} not found"
            )
        
        # Fetch matches for this tournament
        matches = pandascore.get_matches(tournament_id=tournament_id)
        
        # Enhance tournament data with matches
        tournament_data["matches"] = matches
        
        return tournament_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_tournament_details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tournament details: {str(e)}"
        )

@app.post("/predictions/{match_id}")
async def create_prediction(
    match_id: str,
    prediction: dict,
    db: Session = Depends(get_db)
):
    try:
        # TODO: Validate match exists and is not finished
        match_data = pandascore.get_match(match_id)
        if not match_data:
            raise HTTPException(
                status_code=404,
                detail=f"Match with ID {match_id} not found"
            )
        
        if match_data.get("status") == "finished":
            raise HTTPException(
                status_code=400,
                detail="Cannot make predictions for finished matches"
            )
        
        # TODO: Save prediction to database
        # For now, just return success
        return {
            "status": "success",
            "message": "Prediction recorded",
            "prediction": prediction
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_prediction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create prediction: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 