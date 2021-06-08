# Running notebooks

You may need to install `jupyter-lab` package inside CLAP's virtual environment to
run the notebooks. Use the command

`pip install jupyterlab`

Then, in the CLAP root directory and inside `clap-env` virtual environment, run 
the command 

`(clap-env) user@machine:~/CLAP$ jupyter-lab`

In the browser, navigate to `examples` directory to run the notebooks.

In `api` directory you may find examples on how to use CLAP's python API.

In `cli` directory you may find examples on how to use CLAP's CLI tools, such as 
how to create a cluster to install, compile, run and fetch results from 
[NAS Parallel MPI Benchmarks](https://www.nas.nasa.gov/publications/npb.html).

