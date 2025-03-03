from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True)
    name = Column(String)
    game = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(String)
    prize_pool = Column(String)
    teams = relationship("Team", secondary="tournament_teams")

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True)
    name = Column(String)
    acronym = Column(String)
    image_url = Column(String)
    game = Column(String)
    rating = Column(Float, default=1500.0)  # Initial ELO rating
    tournaments = relationship("Tournament", secondary="tournament_teams")

class TournamentTeam(Base):
    __tablename__ = "tournament_teams"

    tournament_id = Column(Integer, ForeignKey("tournaments.id"), primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), primary_key=True) 