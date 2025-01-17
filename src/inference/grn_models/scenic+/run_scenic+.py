import os
import dill
import argparse
import muon as mu
import numpy as np
from scenicplus.scenicplus_class import create_SCENICPLUS_object
from scenicplus.wrappers.run_scenicplus import run_scenicplus
from scenicplus.preprocessing.filtering import apply_std_filtering_to_eRegulons


# Init args
parser = argparse.ArgumentParser()
parser.add_argument('-i','--path_input', required=True)
parser.add_argument('-c','--path_cistopic_obj', required=True)
parser.add_argument('-m','--path_motif_enrichment', required=True)
parser.add_argument('-o','--organism', required=True)
parser.add_argument('-s', '--path_scenicplus_obj', required=True)
parser.add_argument('-g', '--path_grn', required=True)
parser.add_argument('-r', '--path_r2g', required=True)
parser.add_argument('-t', '--path_tri', required=True)

args = vars(parser.parse_args())
path_input = args['path_input']
path_cistopic_obj = args['path_cistopic_obj']
path_motif_enrichment = args['path_motif_enrichment']
organism = args['organism']
path_scenicplus_obj = args['path_scenicplus_obj']
path_grn = args['path_grn']
path_r2g = args['path_r2g']
path_tri = args['path_tri']

# Read rna adata
adata = mu.read(path_input)
del adata.mod['atac']
obs = adata.obs.copy()
adata = adata.mod['rna'].copy()
adata.obs = obs
adata.X = adata.layers["counts"]

# Read cisTopic object
cistopic_obj = dill.load(open(path_cistopic_obj, 'rb'))

# Load motif enrichment object
menr = dill.load(open(path_motif_enrichment, 'rb'))

# Create SCENICPLUS object
scplus_obj = create_SCENICPLUS_object(
    GEX_anndata = adata,
    cisTopic_obj = cistopic_obj,
    menr = menr,
)
scplus_obj.X_EXP = np.array(scplus_obj.X_EXP.todense())

# Select dbs
if organism == 'human':
    species = "hsapiens"
    assembly = "hg38"
    tf_file = "resources/tf_lists/human.txt"
    biomart_host = "http://sep2019.archive.ensembl.org/"

# Run SCENIC+
path_output = os.path.dirname(path_scenicplus_obj)
try:
    run_scenicplus(
        scplus_obj = scplus_obj,
        variable = ['GEX_celltype'],
        species = species,
        assembly = assembly,
        tf_file = tf_file,
        save_path = path_output,
        biomart_host = biomart_host,
        upstream = [1000, 150000],
        downstream = [1000, 150000],
        calculate_TF_eGRN_correlation = True,
        calculate_DEGs_DARs = False,
        export_to_loom_file = False,
        export_to_UCSC_file = False,
        path_bedToBigBed = 'resources/bin',
        n_cpu = 1,
        _temp_dir="/cellar/users/aklie/tmp",  # TODO: no hardcoding
    )
except Exception as e:
    dill.dump(scplus_obj, open(path_scenicplus_obj, 'wb'), protocol=-1)
    print(e, "\nSCENIC+ object saved to", path_scenicplus_obj)

# Save pipeline outputs
apply_std_filtering_to_eRegulons(scplus_obj)

# grn
grn = scplus_obj.uns["TF2G_adj"][["TF", "target", "importance_x_rho"]]
grn.columns = ["source", "target", "weight"]
grn["pval"] = 1
grn.to_csv(path_grn, sep="\t", index=False)

# r2g
r2g = scplus_obj.uns["region_to_gene"] \
    .rename(columns={"importance_x_rho": "weight"})
r2g["pval"] = 1
r2g.drop(columns=["Distance"], inplace=True)
r2g = r2g[["target", "region", "weight", "pval", "importance", "rho"]]
r2g.to_csv(path_r2g, sep="\t", index=False)

# tri
tri = scplus_obj.uns["eRegulon_metadata"]
tri["weight"] = tri[["R2G_importance_x_rho", "TF2G_importance_x_rho"]].mean(axis=1)
tri["pval"] = 1
tri["region"] = tri["Region"].str.replace(":", "-")
tri = tri.rename(columns={"TF": "source", "Gene": "target"})
tri = tri[["source", "target", "region", "weight", "pval", "is_extended", 
           "R2G_importance", "R2G_rho", "R2G_importance_x_rho",
           "R2G_importance_x_abs_rho", "TF2G_importance", "TF2G_regulation",
           "TF2G_rho", "TF2G_importance_x_abs_rho", "TF2G_importance_x_rho"]]
tri.to_csv(path_tri, sep="\t", index=False)
