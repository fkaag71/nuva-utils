from rdflib import *
from urllib.request import urlopen,urlretrieve
from pathlib import Path
import csv
import json
import os
import math
from tkinter import *
from tkinter import filedialog

BaseURI="http://ivci.org/NUVA/"

            
def eval_code(filename,option):
    if option == 1:
        suffix="_full"
        fullset = True
    else:
        suffix="_gen"
        fullset = False

    say ("Loading code graph")

    csv_file = open(filename,'r',encoding="utf-8-sig",newline='')
    reader = csv.DictReader(csv_file,delimiter=';')
    code = reader.fieldnames[0]

    Path(code).mkdir(parents=True,exist_ok=True)

    rev_fname = code+"/nuva_reverse_"+code+suffix+".csv"
    best_fname=code+"/nuva_best_"+code+suffix+".csv"
    metrics_fname = code+"/nuva_metrics_"+code+suffix+".txt"

    codeParent=URIRef(BaseURI+code)
    if ((codeParent,None,None) not in g):
        g.add((codeParent,RDFS.Class,OWL.Class))
        g.add((codeParent,RDFS.subClassOf,URIRef(BaseURI+'Code')))
        g.add((codeParent,RDFS.label,Literal(code)))

    for row in reader:
        codeURI=URIRef(BaseURI+row[code])
        nuvaURI=URIRef(BaseURI+row["NUVA"])
        if ((nuvaURI,None,None) not in g):
            say ("Mapping to unknown NUVA code "+row["NUVA"])            

        codeValue=row[code].rsplit('-')[1]

        g.add((nuvaURI,SKOS.exactMatch,codeURI))
        g.add((codeURI,RDFS.Class,OWL.Class))
        g.add((codeURI,RDFS.subClassOf,codeParent))
        g.add((codeURI,SKOS.notation,Literal(codeValue)))
        g.add((codeURI,RDFS.label,Literal(row[code])))
        
    csv_file.close 

    #if os.path.isfile(work_fname): g.parse(work_fname)
    #else: g.parse(ref_fname)

    say ("Retrieve the list of NUVA codes")
    q1="""
    SELECT ?vacnot ?label ?abstract WHERE {
      ?vac rdfs:subClassOf nuva:Vaccine .
      ?vac skos:notation ?vacnot .
      ?vac rdfs:label ?label filter(lang(?label)='en'||lang(?label)='') .
      ?vac nuvs:isAbstract ?abstract .
      """
    if not fullset:
      q1 += """
      ?vac nuvs:isAbstract true
      """                
    q1 += """        
    } ORDER BY ?vacnot
    """
    res1 = g.query(q1)
    
    bestcodes = {}
    revcodes = {}
    nbequiv = {}

    for row in res1:
        bestcodes[str(row.vacnot)] = {'label':str(row.label),'cardinality':10000,'isAbstract':str(row.abstract), 'codes':[]}
        
    nbnuva = len(bestcodes)

    #if fullset:
    say("Retrieve NUVA codes matching specific external codes")    
    q2="""
    SELECT ?extnot ?rlabel ?rnot ?abstract WHERE { 
    ?extcode rdfs:subClassOf nuva:"""+code+""" .
    ?extcode skos:notation ?extnot .
    ?rvac rdfs:subClassOf nuva:Vaccine . 
    ?rvac rdfs:label ?rlabel .
    ?rvac skos:exactMatch ?extcode .
    ?rvac skos:notation ?rnot .
    ?rvac nuvs:isAbstract ?abstract .
    } 
    """
    res2 = g.query(q2)
    for row in res2:
        extnot = code+"-"+str(row.extnot)
        nuva_code = str(row.rnot)
        if nuva_code in nbequiv:
            nbequiv[nuva_code] += 1
        else:
            nbequiv[nuva_code] =1
            
        if (fullset and str(row.abstract)=='false'):
            revcodes[extnot]= {"label" : str(row.rlabel), "cardinality" : 1, "may": [nuva_code], "blur":0, "best": []}
            bestcodes[nuva_code]['cardinality'] = 1
            bestcodes[nuva_code]['codes'].append(extnot)


    say("Retrieve NUVA codes matching abstract external codes")    
    q3="""
   SELECT ?extnot ?rlabel ?rnot (count(?codevac) as ?nvac) (GROUP_CONCAT(?vacnot) as ?lvac) WHERE { 
   ?extcode rdfs:subClassOf nuva:"""+code+""" .
   ?extcode skos:notation ?extnot .
   ?rvac rdfs:subClassOf nuva:Vaccine . 
   ?rvac skos:exactMatch ?extcode .
   ?rvac skos:notation ?rnot .
   ?rvac rdfs:label ?rlabel .
   ?rvac nuvs:isAbstract true .
   ?vac rdfs:subClassOf nuva:Vaccine .
   """
    if not fullset:
       q3+= """?vac nuvs:isAbstract true .
       """
    q3+= """
   ?vac skos:notation ?vacnot
    FILTER NOT EXISTS {
    # The reference vaccine ?rvac for the external code does not have any valence not within the ?vac candidate
    # Considering all valences within ?rvac
   # Keep the ones that do not have a child in the candidate ?vac
   # If the list is not empty, the candidate is discarded
        ?rvac nuvs:containsValence ?rval .
        FILTER NOT EXISTS {
            ?vac nuvs:containsValence ?val .
            ?val rdfs:subClassOf* ?rval
        }
    } .
 FILTER NOT EXISTS {
 # The ?vac candidate does not have any valence not present in the reference vaccine ?rvac
 # Considering all valences of the candidate ?vac
 # We keep the ones that do not have a parent in the reference ?rvac
 # If the list is not empty, the candidate is discarded
       ?vac nuvs:containsValence ?val .
        FILTER  NOT EXISTS {
            ?rvac nuvs:containsValence ?rval .
            ?val rdfs:subClassOf* ?rval
        }
    }
 } GROUP BY ?extnot ?rlabel ?rnot ?abstract
   """
    res3=g.query(q3)

    for row in res3:
        extnot = code+"-"+str(row.extnot)
        rnot = str(row.rnot)
        
        nuva_codes=row.lvac.split()
         
        rcard = len(nuva_codes)                  
        revcodes[extnot]= {"label" : str(row.rlabel), "cardinality" : rcard, "may": [], "blur":0, "best": []}

        for nuva_code in nuva_codes:
            revcodes[extnot]['may'].append(nuva_code)
            if (bestcodes[nuva_code]['cardinality'] == rcard):
                bestcodes[nuva_code]['codes'].append(extnot)
                continue
            if (bestcodes[nuva_code]['cardinality'] > rcard):
                bestcodes[nuva_code]['cardinality'] = rcard
                bestcodes[nuva_code]['codes']=[extnot]


    say ("Create best codes report "+best_fname)
    best_file = open(best_fname,'w',encoding="utf-8",newline='')
    best_writer = csv.writer(best_file, delimiter=';')
    best_writer.writerow(["NUVA","Label","IsAbstract", "Cardinality","Best "+code])
    unmapped = 0
    totalcount = 0
    nuva_equiv = total_equiv = 0
    for nuva_code in bestcodes:
        best_writer.writerow([nuva_code,bestcodes[nuva_code]['label'],bestcodes[nuva_code]['isAbstract'],
                              bestcodes[nuva_code]['cardinality'], bestcodes[nuva_code]['codes']])
        if bestcodes[nuva_code]['cardinality'] ==  10000 :  unmapped +=1
        else:
            for extcode in bestcodes[nuva_code]['codes']:
                revcodes[extcode]['blur'] +=1
                revcodes[extcode]['best'].append(nuva_code)
        if nuva_code in nbequiv and nbequiv[nuva_code] != 0:
            nuva_equiv += 1
            total_equiv += nbequiv[nuva_code]
    best_file.close

    say ("Create reverse codes report "+rev_fname)
    rev_file = open(rev_fname,'w',encoding="utf-8",newline='')
    rev_writer = csv.writer(rev_file, delimiter=';')
    rev_writer.writerow([code,"Label","Cardinality","May code", "Blur", "Best code for"])

    totalblur = 0
    for extcode in revcodes:
        rev_writer.writerow([extcode,revcodes[extcode]['label'], 
                             revcodes[extcode]['cardinality'],revcodes[extcode]['may'], 
                             revcodes[extcode]['blur'], revcodes[extcode]['best']])
        totalblur += revcodes[extcode]['blur']
    rev_file.close

    # All aligned codes, abstract or not, are now in rev_codes
    nbcodes = len(revcodes)

    completeness = (nbnuva-unmapped)/nbnuva
    precision = 0
    if totalblur != 0:
        precision = nbcodes/totalblur
    redundancy = 0
    if nuva_equiv != 0:
        redundancy = total_equiv/nuva_equiv

    say ("Create metrics report "+metrics_fname)
    metrics_file = open(metrics_fname,'w',encoding="utf-8",newline='')
    print (f"NUVA version :{g.value(URIRef('http://ivci.org/NUVA'),OWL.versionInfo)}\n", file=metrics_file)
    print (f"Number of NUVA concepts : {nbnuva}",file=metrics_file)
    print (f"Number of unmapped concepts: {unmapped}",file=metrics_file)
    print ("Completeness: {:.1%}\n".format(completeness),file=metrics_file)
    print (f"Number of aligned codes: {nbcodes}",file=metrics_file)
    print ("Average blur of aligned codes {:.1f}".format(1/precision),file=metrics_file)
    print ("Precision: {:.1%}".format(precision),file=metrics_file)
    print ("Redundancy: {:.3}".format(redundancy),file=metrics_file)
    metrics_file.close()
    Message.set("Select a CSV file")

def say(text):
    result.insert('end','\n'+text)
    root.update()

def get_file():
    result.delete('1.0',END)
    filename = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
    if filename != '':
        Message.set("Processing")
        os.chdir(os.path.dirname(filename))
        eval_code(filename, var.get())


root = Tk()
var = IntVar()
frame = Frame()
frame.pack()
R1 = Radiobutton(frame, text="All concepts", variable=var, value=1)
R1.pack( side=LEFT )
R1.select()
R2 = Radiobutton(frame, text="Abstract vaccines", variable=var, value=2)
R2.pack( side = LEFT )
Message = StringVar()
Label = Label(root,textvariable = Message)
Label.pack()
Message.set("Loading core graph, please wait.")
root.update()

nuva_file = urlopen("https://ivci.org/nuva/nuva_core.ttl")
g = Graph(store="Oxigraph")
g.parse(nuva_file.read())

Message.set("Select a CSV file")
actFile = Button(root,text='Select', command = get_file)
actFile.pack()
result=Text(root,width=100,height=10)
result.pack()

root.mainloop()



