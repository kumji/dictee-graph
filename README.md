# Dictee LOD Graph

Linked Open Data model of Theresa Hak Kyung Cha's *Dictee* (Tanam Press, 1982),
accompanying the article "Modeling the Unnameable: A Linked Open Data Schema for the Artist's Book Dictee by Theresa Hak Kyung Cha" (under review).

- Graph viewer: https://kumji.github.io/dictee-graph/
- Property definitions: https://kumji.github.io/dictee-graph/prop/
- Data: `data/` (CSV), `public/data/graph.jsonld` (Linked Art JSON-LD)

## Build

```bash
npm install
./scripts/run-all.sh
```

Requires Python 3 (PyYAML) and Node.js 20. The script converts the CSV files to
JSON-LD, generates the entity and property pages, and then starts a local dev
server. Validation logs are written to `logs/`.

## License

Data (`data/`, `public/data/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · Code: [MIT](LICENSE)

## Authors

- Eunji Park: research design, data curation, schema design
- Kumji Park: pipeline and web implementation
