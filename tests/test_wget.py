import bz2
import os
import shutil
import time

BASE_URL = "https://opendata.dwd.de/climate_environment/REA/COSMO_REA6/hourly/2D/SWDIFDS_RAD/"
src = "."  # Change as needed
os.makedirs(src, exist_ok=True)


def decompress_bz2(src, dest):
    with bz2.open(src, 'rb') as f_in, open(dest, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)


def main():
    year = 2018
    months = range(1, 13)
    total_start = time.time()
    for m in months:
        code = f"{year}{m:02d}"
        fname = f"SWDIFDS_RAD.2D.{code}.grb.bz2"
        bz2_path = os.path.join(src, fname)
        grb_path = bz2_path[:-4]  # remove .bz2

        print(f"\nProcessing {fname} ...")
        t0 = time.time()

        # Decompress
        if not os.path.exists(grb_path):
            print(f"Decompressing {bz2_path} ...")
            t_dc0 = time.time()
            decompress_bz2(bz2_path, grb_path)
            t_dc1 = time.time()
            print(f"Decompression done in {t_dc1-t_dc0:.2f} s")
        else:
            print("File already decompressed.")

        t1 = time.time()
        print(f"Total time for {fname}: {t1-t0:.2f} s")

    print(f"\nTotal elapsed time: {time.time()-total_start:.2f} s")


if __name__ == "__main__":
    main()
