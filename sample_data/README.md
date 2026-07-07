# sample_data

Drop a few drone images here (`.jpg` / `.tiff`) to test Layer 1, then run:

```bash
python -m scripts.run_detection sample_data
```

Geotagged images (e.g. DJI photos with EXIF GPS) will have their coordinates
decoded and shown in the batch summary / report.
