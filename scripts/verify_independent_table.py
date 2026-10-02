"""Compare derived results to transcribed independent NBC final standings."""
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
source = pd.read_csv(ROOT / 'qa/Independent_Table_NBC.csv').set_index('Team')
actual = pd.read_csv(ROOT / 'outputs/actual_rebuilt_table.csv').set_index('Team')
rows = []
for team in source.index:
    for field in ['Rank', 'W', 'D', 'L', 'GD', 'Pts']:
        a, b = int(source.loc[team, field]), int(actual.loc[team, field])
        rows.append({'Team': team, 'Field': field, 'NBC_published': a, 'CSV_rebuilt': b, 'Match': a == b})
comparison = pd.DataFrame(rows)
comparison.to_csv(ROOT / 'qa/Independent_Table_Comparison.csv', index=False)
matched = int(comparison.Match.sum())
print(f'Independent NBC comparison: {matched}/{len(comparison)} numerical fields agree.')
print(comparison.loc[~comparison.Match].to_string(index=False))
print('NBC is an independent publisher, not the official Premier League table; GF/GA not provided. Official full-table verification remains pending.')
