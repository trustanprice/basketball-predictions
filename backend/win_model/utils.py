# utils.property

# necessary for data leak checks
nba_teams = [
    'Atlanta Hawks','Boston Celtics','Brooklyn Nets','Charlotte Hornets',
    'Chicago Bulls','Cleveland Cavaliers','Dallas Mavericks','Denver Nuggets',
    'Detroit Pistons','Golden State Warriors','Houston Rockets','Indiana Pacers',
    'Los Angeles Clippers','Los Angeles Lakers','Memphis Grizzlies','Miami Heat',
    'Milwaukee Bucks','Minnesota Timberwolves','New Orleans Pelicans','New York Knicks',
    'Oklahoma City Thunder','Orlando Magic','Philadelphia 76ers','Phoenix Suns',
    'Portland Trail Blazers','Sacramento Kings','San Antonio Spurs','Toronto Raptors',
    'Utah Jazz','Washington Wizards'
]

# Map of acronyms to full team names
team_map = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BRK": "Brooklyn Nets",  # sometimes shown as BRK or BKN
    "BKN": "Brooklyn Nets",
    "CHI": "Chicago Bulls",
    "CHO": "Charlotte Hornets",  # CHA/CHO both used historically
    "CHA": "Charlotte Hornets",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards"
}
