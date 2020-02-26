# -*- coding: utf-8 -*-
"""
Runs p13CMFA
--iso2flux_model_file=,-I (mandatory):  path to the iso2flux model where p13cmfa will be applied. Generally, the selected Iso2flux model should be the one generated by the solve_iso2flux_label.py script to use the 13CMFA solution as starting point. 
--output_prefix=","-o= (optional): Used to define a prefix that will be added to all output files. It can be used both to name the outputs and to select the directory where the outputs will be saved (directory must already exist)
--number_of_processes=,-n(optional): Number of islands (processes) that will be used in the optimization. Should not be larger than the number of processor threads. Default is 4.  
--population_size=(optional),-p(optional):  Size of the population in each island. Default is 20. 
--generations_per_cycle=,-g(optional):  Number of generations that each island will evolve before exchanging individuals with other islands. Default is 200.
--max_cycles_without_improvement=,-m (optional): Maximum number of cycles without a significant improvement of the objective function. When this number is reached the algorithm will stop. Default is 9 
--flux_penalty_file=,-f (optional): path to the flux_penalty_file, this file defines the weight given to the minimization of each flux. 
--absolute, -a (optional) If this flag is used the tolerance will be used as an absolute tolerance
 --tolerance_of_label_objective=,-t(optional): Tolerance of the primary  13C MFA objective in the p13cmfa optimization. If the absolute flag is not used the maximum primary objective allowed value will be the optimal value of the primary objective plus the tolerance_of_label_objective. The optimal value of the primary objective will be taken from the iso2flux_model_file if solve_iso2flux_label.py  has been run with this model. Alternatively, 13C MFA will be run to find the optimal value of the primary objective. If the absolute flag is used, the tolerance_of_label_objective will be the absolute maximum value allowed for the primary objective. Default is 3.84
--starting_flux_value,-s (optional): Initial estimation of the minimal flux value, the script will only sample solutions bellow or equal this value. Default is 1e6 
--cycles=,-c (optional): number of iterations that the script should be run. In complex models the script might not be able to find the absolute minimum in just one iteration, running several iterations increases the likelihood that the absolute minimum has been found.

"""
import tkFileDialog
import Tkinter
import sys, getopt
import numpy as np
import copy
import os



from iso2flux import fitting
from iso2flux.misc.save_load_iso2flux_model import load_iso2flux_model, save_iso2flux_model
from iso2flux.flux_functions.minimal_flux import create_minimal_fux_model,flux_minimization_fva
from iso2flux.fitting.variable_sampling import variable_sampling
from iso2flux.fitting.get_variable_bounds import get_variable_bounds
from iso2flux.fitting.objfunc import objfunc
from iso2flux.fitting.extract_results import extract_results
from iso2flux.output_functions.write_fluxes import export_flux_results
from iso2flux.output_functions.export_label_results import export_label_results
from iso2flux.fitting.optimize import optimize,minimize_fluxes,define_isoflux_problem
from iso2flux.flux_functions.build_flux_penalty_dict import build_flux_penalty_dict, add_gene_expression_to_flux_penalty,write_flux_penalty_dict,read_flux_penalty_dict_from_file


try:
 argv=sys.argv[1:]
 opts, args = getopt.getopt(argv,"i:f:n:p:g:m:o:t:as:c:x:",["iso2flux_model_file=","flux_penalty_file=","number_of_processes=","population_size=","generations_per_cycle=","max_cycles_without_improvement=","output_prefix=","tolerance_of_label_objective=","absolute","starting_flux_value=","cycles=","max_flux_for_sampling="])
except getopt.GetoptError as err:
   print str(err)  # will print something like "option -a not recognized":
   sys.exit(2)


pop_size=20
n_gen=200
number_of_processes=6
output_prefix=None
flux_penalty_file=None
objective_tolerance=3.84
relative_tolerance=True
initial_flux_estimation=None
n_iterations=1
max_cycles_without_improvement=9 
file_name=None
max_flux_for_sampling=1e-6

for opt, arg in opts:
         print [opt,arg]
         if opt in ("--iso2flux_model_file","-i"):
             file_name=arg
         elif opt in ("--number_of_processes","-n"):
             number_of_processes=int(arg)            
         elif opt in ("--output_prefix","-o"):
             output_prefix=arg
         elif opt in ("--population_size","-p"):
             pop_size=int(arg)
         elif opt in ("--generations_per_cycle","-g"):
             n_gen=int(arg)
         elif opt in ("--flux_penalty_file","-f"):
             flux_penalty_file=arg
         elif opt in ("--tolerance_of_label_objective","-t"):
             objective_tolerance=float(arg)
         elif opt in ("--absolute","-a"):
             relative_tolerance=False
         elif opt in ("--starting_flux_value","-s"):
             initial_flux_estimation=float(arg)
         elif opt in ("--cycles","-c"):
             n_iterations=int(arg)
         elif opt in ("--max_cycles_without_improvement","-m"):
             max_cycles_without_improvement=int(arg)
         elif opt in ("--max_flux_for_sampling","-x"):
             max_flux_for_sampling=float(arg)


 

if file_name==None:
    tk=Tkinter.Tk()
    tk.withdraw()
    loaded_file = tkFileDialog.askopenfile(title='Select iso2flux file',filetypes=[("iso2flux",".iso2flux")]) 
    file_name=loaded_file.name
    tk.destroy()

print "file_name",file_name


if ".iso2flux" not in file_name:
    file_name+=".iso2flux"


if output_prefix==None:
   output_prefix=file_name.split("/")[-1].replace(".iso2flux","") 
     




label_model=load_iso2flux_model(file_name)


default_name_flux_dict=file_name.replace(".iso2flux","_flux_penalty.csv")
if flux_penalty_file==None:
   #Try to see if the flux_penalty dict saved with the default name exists
   try:
     flux_penalty_dict=read_flux_penalty_dict_from_file(default_name_flux_dict)
   except:
     raise Exception("Flux penalty for "+file_name+" "+default_name_flux_dict+" not found" )
     
else:
   print "loading "+flux_penalty_file
   flux_penalty_dict=read_flux_penalty_dict_from_file(flux_penalty_file)




iso2flux_problem=define_isoflux_problem(label_model)
#Get the best fit from iso2flux model, if does not exist run a simulation to get it
if relative_tolerance:
   if label_model.best_label_variables!=None:
      best_label_variables=label_model.best_label_variables
      a,objective_dict=objfunc(label_model,best_label_variables,flux_penalty_dict=flux_penalty_dict,flux_weight=1)
   else:
      label_problem_parameters={"label_weight":1,"target_flux_dict":None,"max_chi":1e6,"max_flux":1e6,"flux_penalty_dict":{},"verbose":True,"flux_weight":0.0,"label_unfeasible_penalty":1.0,"flux_unfeasible_penalty":10}
      best_objective,best_label_variables=optimize(label_model,iso2flux_problem,pop_size ,n_gen ,n_islands=number_of_processes,max_evolve_cycles=999,max_cycles_without_improvement=9,stop_criteria_relative=0.0005,stop_criteria_absolute=-1e6,initial_archi_x=[],lb_list=[],ub_list=[],flux_penalty_dict=None,max_flux=None,label_problem_parameters=label_problem_parameters,min_model=None,extra_constraint_dict={})
      label_model.best_label_variables=list(best_label_variables)
   
   a,objective_dict=objfunc(label_model,best_label_variables,flux_penalty_dict=flux_penalty_dict,flux_weight=1)
   max_chi=objective_dict["chi2_score"]+objective_tolerance
   
else:
  max_chi=objective_tolerance

if initial_flux_estimation==None:
   if label_model.best_p13cmfa_variables!=None:
      a,objective_dict=objfunc(label_model,label_model.best_p13cmfa_variables,flux_penalty_dict=flux_penalty_dict,flux_weight=1)
      initial_flux_estimation=objective_dict["flux_score"]
   elif label_model.best_label_variables!=None:
      a,objective_dict=objfunc(label_model,best_label_variables,flux_penalty_dict=flux_penalty_dict,flux_weight=1)
      initial_flux_estimation=objective_dict["flux_score"]
   else:
      initial_flux_estimation=999999





label_problem_parameters={"label_weight":0.0001,"target_flux_dict":None,"max_chi":max_chi,"max_flux":initial_flux_estimation,"flux_penalty_dict":flux_penalty_dict,"verbose":True,"flux_weight":1,"flux_unfeasible_penalty":25,"label_unfeasible_penalty":5}

best_flux=initial_flux_estimation
best_variables=None


for iteration in range(0,n_iterations):
    flux_objective,variables=minimize_fluxes(label_model,iso2flux_problem,label_problem_parameters,max_chi=max_chi,flux_penalty_dict=flux_penalty_dict ,pop_size=pop_size ,n_gen=n_gen ,n_islands=number_of_processes ,max_cycles_without_improvement=max_cycles_without_improvement ,max_evolve_cycles=999 ,stop_criteria_relative=0.000001 ,max_iterations=1,  initial_flux_estimation=initial_flux_estimation,log_name=file_name.replace(".iso2flux","_p13cmfa_log.txt"),migrate="one_direction",max_flux_sampling=max_flux_for_sampling)
    print "flux minimized to " + str(round(flux_objective,3))
    if flux_objective<best_flux:
       initial_flux_estimation=best_best_flux=flux_objective
       label_problem_parameters={"label_weight":0.0001,"target_flux_dict":None,"max_chi":max_chi,"max_flux":best_flux,"flux_penalty_dict":flux_penalty_dict,"verbose":True,"flux_weight":1,"flux_unfeasible_penalty":25,"label_unfeasible_penalty":5}
       best_best_flux=flux_objective
       best_variables=variables



export_flux_results(label_model,best_variables,fn=output_prefix+"_p13cmfa_fluxes.csv")
export_flux_results(label_model,best_variables,fn=output_prefix+"_p13cmfa_fluxes_irreversible.csv",reversible=False)

objfunc(label_model,best_variables)
export_label_results(label_model,fn=output_prefix+"_p13cmfa_label.csv",show_chi=True,show_emu=True,show_fluxes=False)
np.savetxt(output_prefix+"_p13cmfa_variables.txt",best_variables)
label_model.best_p13cmfa_variables=best_variables
label_model.label_tolerance=max_chi
label_model.best_flux=flux_objective

print label_model.label_tolerance

save_iso2flux_model(label_model,name=output_prefix+".iso2flux",write_sbml=True,ask_sbml_name=False,gui=False)

