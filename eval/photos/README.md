# Put your stream photographs in this folder

Drop `.jpg`, `.jpeg`, `.png` or `.webp` files straight in here — no subfolders,
any filename. Twenty to thirty is a good number to start with.

Then:

```bash
python eval/make_labels.py   # builds eval/labels.csv, one row per photo per question
python eval/run_eval.py      # measures the prompt and writes eval/reports/
```

**The images themselves are not committed** (`.gitignore` excludes everything in
here except this README). That keeps third-party licensing out of the repository
— see `docs/photo-sources.md` for where to find usable images and what each
licence asks of you.

Aim for a spread rather than twenty photos of the same pretty stream: concrete
channel, natural gravel bed, dry bed, foamy or discoloured water, a heavily
vegetated bank, a bare paved bank, a weir, a pipe outfall. The point is to find
where the prompt breaks, not to confirm that it works.
