"""Integration check for generated rankings and the local browser UI."""
import json
from pathlib import Path
import app


def main():
    c = app.app.test_client()
    data = c.get('/api/dataset?set=fei')
    assert data.status_code == 200
    records = data.json['pictures']
    assert len(records) == 2800
    assert len({r['participant'] for r in records}) == 200
    assert all(sum(p['participant'] == r['participant'] for p in records) == 14 for r in records)
    assert len({r['id'] for r in records}) == 2800
    assert [p['rank'] for p in records] == list(range(1, 2801))
    assert all(1 <= p['score'] <= 7 and p['age_range'] == '19–40' for p in records)
    assert all(records[i]['score'] >= records[i+1]['score'] for i in range(2799))
    assert data.json['metrics'] is None
    assert all((app.DATA / 'fei' / 'images' / p['filename']).is_file() for p in records)
    assert c.get('/dataset-images/fei/' + records[0]['filename']).status_code == 200
    assert c.get('/api/dataset?set=../').status_code == 400
    assert c.get('/dataset-images/fei/../../app.py').status_code == 404
    assert c.get('/api/dataset').json['metrics']['subjects'] == 100
    assert c.get('/api/pictures').json['total'] == 13
    print('PASS: FEI count, subject grouping, scores, order, previews, routes, original datasets')


if __name__ == '__main__':
    main()
