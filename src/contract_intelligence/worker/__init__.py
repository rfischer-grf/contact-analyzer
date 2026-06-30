"""Worker Temporal : saga d'ingestion (cf. spec §4).

Le module `states` est pur (sans dépendance temporalio) et donc importable partout ;
`workflows`/`activities`/`bootstrap` requièrent l'extra `worker` (`pip install .[worker]`).
"""
