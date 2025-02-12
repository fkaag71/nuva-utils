from rdflib import *
from urllib.request import urlopen,urlretrieve
from pathlib import Path
import csv
import json
import os
import shutil
import math

BaseURI="http://ivci.org/NUVA/"
full_fname="nuva_ivci.rdf"
core_fname ="nuva_core.ttl"


def get_nuva_version():
    url="https://ans.mesvaccins.net/last_version.json"
    response=urlopen(url)
    data_json=json.loads(response.read())
    return (data_json['version'])

def get_nuva(version):
  print ("Retrieving NUVA version "+version)
  fname1 = "nuva_ans.rdf";
  urlretrieve("https://ans.mesvaccins.net/versions/"+version+"/nuva.rdf",fname1)

  # Change base URL
  f1= open(fname1,'r',encoding="utf-8")
  f2= open(full_fname,'w',encoding="utf-8")
  for line in f1:
      relocated = line.replace("data.esante.gouv.fr","ivci.org")
      f2.write(relocated.replace("NUVA#","NUVA/"))
  f1.close()
  f2.close()

def split_nuva():
    print ("Loading graph to split")
    g = Graph()
    g.parse(full_fname)

    CodesParent=URIRef(BaseURI+"Code")
    graph_codes = {}
    graph_langs = {}

    print("Initializing subgraphs for code systems")
    Codes = g.subjects(RDFS.subClassOf,CodesParent)
    for Code in Codes:
        label=g.value(Code,RDFS.label)
        graph_codes[label] = Graph(store="Oxigraph")

    print("Initializing core graph")    
    g_core= Graph(store="Oxigraph")
    
    for s,p,o in g:

        # Extract languages
        if (o.__class__.__name__== "Literal"):
            lang = o.language
            if (lang!="en" and lang!=None): 
                if (not lang in graph_langs.keys()):
                    graph_langs[lang] = Graph(store="Oxigraph");
                graph_langs[lang].add((s,p,o))
                continue

        # Extract properties of external codes
        sparent=g.value(s,RDFS.subClassOf)
        if (g.value(sparent,RDFS.subClassOf) == CodesParent):
            system = g.value(sparent,RDFS.label)
            graph_codes[system].add((s,p,o))
            continue

        # Extract binding of external codes
        oparent=g.value(o,RDFS.subClassOf)
        if (g.value(oparent,RDFS.subClassOf) == CodesParent):
            system = g.value(oparent,RDFS.label)
            graph_codes[system].add((s,p,o))
            continue

        # Otherwise the triple goes to core graph
        g_core.add((s,p,o))

    NUVS = Namespace("http://ivci.org/NUVA/nuvs#")
    NUVA = Namespace("http://ivci.org/NUVA/") 
    g_core.bind("nuvs",NUVS)
    g_core.bind("nuva",NUVA)

    print(f"Core NUVA has {len(g_core)} statements.")
    g_core.serialize(destination=core_fname)

    for lang in graph_langs:
        print(f"There are {len(graph_langs[lang])} statements for language {lang}.")
        fname = "nuva_lang_"+lang+".ttl"
        graph_langs[lang].serialize(destination=fname)

    for code in graph_codes:
        print(f"There are {len(graph_codes[code])} statements for code {code}.")
        fname = "nuva_refcode_"+code+".ttl"
        graph_codes[code].serialize(destination=fname)

def refturtle_to_map(code):
    ttl_fname = "nuva_refcode_"+code+".ttl"
    csv_fname = "nuva_refcode_"+code+".csv"
    g = Graph(store="Oxigraph")
    g_core = Graph(store="Oxigraph")

    g_core.parse(core_fname)
    g.parse(ttl_fname)

    csv_file = open(csv_fname,'w',encoding="utf-8",newline='')
    writer = csv.writer(csv_file, delimiter=';')
    writer.writerow([code,"NUVA","Label"])

    for s,p,o in g.triples((None,SKOS.exactMatch,None)):
        label = g_core.value(s,RDFS.label)
        writer.writerow([o.split('/')[-1],s.split('/')[-1],label])
    csv_file.close

def map_to_turtle(code):
        core_fname = "nuva_core.ttl"
        ttl_fname = "nuva_code_"+code+".ttl"
        csv_fname = "nuva_code_"+code+".csv"
        g = Graph(store="Oxigraph")
        g_core=Graph(store="Oxigraph")
        g_core.parse (core_fname)

        codeParent=URIRef(BaseURI+code)
        if ((codeParent,None,None) not in g_core):
            print ("Unknown CodeSystem "+code)
            return

        csv_file = open(csv_fname,'r',encoding="utf-8",newline='')
        reader = csv.DictReader(csv_file,delimiter=';')

        for row in reader:
            codeURI=URIRef(BaseURI+row[code])
            nuvaURI=URIRef(BaseURI+row["NUVA"])
            if ((nuvaURI,None,None) not in g_core):
                print ("Mapping to unknown NUVA code "+row["NUVA"])
                return

            codeValue=row[code].rsplit('-')[1]

            g.add((nuvaURI,SKOS.exactMatch,codeURI))
            g.add((codeURI,RDFS.Class,OWL.Class))
            g.add((codeURI,RDFS.subClassOf,codeParent))
            g.add((codeURI,SKOS.notation,Literal(codeValue)))
            g.add((codeURI,RDFS.label,Literal(row[code])))
        
        csv_file.close  
        g.serialize(destination=ttl_fname)

def query_core(q):
    print ("Loading core graph")
    g_core = Graph(store="Oxigraph")
    g_core.parse(core_fname)
    print ("Running query")
    return g_core.query(q)

def query_code(q,code):
    print ("Loading core graph")
    g = Graph(store="Oxigraph")
    g.parse(core_fname)
    print ("Loading code graph")
    print ("nuva_code_"+code+".ttl")
    g.parse("nuva_code_"+code+".ttl")
    print ("Running query")
    return g.query(q)

def lang_table(l1,l2):
    fname1 = "nuva_lang_"+l1+".ttl"
    fname2 = "nuva_lang_"+l2+".ttl"
    csv_fname = "nuva_lang_"+l1+"_"+l2+".csv"

    g1= Graph(store="Oxigraph")
    g1.parse (fname1)
    g2 = Graph(store="Oxigraph")
    g2.parse (fname2)

    csv_file = open(csv_fname,'w',encoding="utf-8",newline='')
    writer = csv.writer(csv_file, delimiter=';')
    writer.writerow([l1,l2])

    for (s,p,o1) in g1:
        o2 = g2.value(s,p,None)
        writer.writerow([o1,o2])
            
def eval_code(code,fullset):
    if fullset:
        suffix="_full"
    else:
        suffix="_gen"
    rev_fname = "nuva_reverse_"+code+suffix+".csv"
    best_fname="nuva_best_"+code+suffix+".csv"
    metrics_fname = "nuva_metrics_"+code+suffix+".txt"
    ref_fname="nuva_refcode_"+code+".ttl"
    work_fname = "nuva_code_"+code+".ttl"

    print ("Loading core graph")
    g = Graph(store="Oxigraph")
    g.parse(core_fname)
    print ("Loading code graph")
    if os.path.isfile(work_fname): g.parse(work_fname)
    else: g.parse(ref_fname)

    print ("Retrieve the list of NUVA codes")
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

    for row in res1:
        bestcodes[str(row.vacnot)] = {'label':str(row.label),'cardinality':10000,'isAbstract':str(row.abstract), 'codes':[]}
        
    nbnuva = len(bestcodes)

    if fullset:
        print("Retrieve NUVA codes matching specific external codes")    
        q2="""
       SELECT ?extnot ?rlabel ?rnot WHERE { 
       ?extcode rdfs:subClassOf nuva:"""+code+""" .
       ?extcode skos:notation ?extnot .
       ?rvac rdfs:subClassOf nuva:Vaccine . 
       ?rvac rdfs:label ?rlabel .
       ?rvac skos:exactMatch ?extcode .
       ?rvac skos:notation ?rnot .
       ?rvac nuvs:isAbstract false .
       } 
       """
        res2 = g.query(q2)
        for row in res2:
            extnot = code+"-"+str(row.extnot)
            nuva_code = str(row.rnot)
                       
            revcodes[extnot]= {"label" : str(row.rlabel), "cardinality" : 1, "may": [nuva_code], "blur":0, "best": []}

            bestcodes[nuva_code]['cardinality'] = 1
            bestcodes[nuva_code]['codes'].append(extnot)

    print("Retrieve NUVA codes matching abstract external codes")    
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


    print ("Create best codes report "+best_fname)
    best_file = open(best_fname,'w',encoding="utf-8",newline='')
    best_writer = csv.writer(best_file, delimiter=';')
    best_writer.writerow(["NUVA","Label","IsAbstract", "Cardinality","Best "+code])
    unmapped = 0
    totalcount = 0
    for nuva_code in bestcodes:
        best_writer.writerow([nuva_code,bestcodes[nuva_code]['label'],bestcodes[nuva_code]['isAbstract'],
                              bestcodes[nuva_code]['cardinality'], bestcodes[nuva_code]['codes']])
        if bestcodes[nuva_code]['cardinality'] ==  10000 :  unmapped +=1
        else:
            for extcode in bestcodes[nuva_code]['codes']:
                revcodes[extcode]['blur'] +=1
                revcodes[extcode]['best'].append(nuva_code)
    best_file.close

    print ("Create reverse codes report "+rev_fname)
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
    precision = nbcodes/totalblur

    print ("Create metrics report "+metrics_fname)
    metrics_file = open(metrics_fname,'w',encoding="utf-8",newline='')
    print (f"NUVA version :{g.value(URIRef('http://ivci.org/NUVA'),OWL.versionInfo)}\n", file=metrics_file)
    print (f"Number of NUVA concepts : {nbnuva}",file=metrics_file)
    print (f"Number of unmapped concepts: {unmapped}",file=metrics_file)
    print ("Completeness: {:.1%}\n".format(completeness),file=metrics_file)
    print (f"Number of aligned codes: {nbcodes}",file=metrics_file)
    print ("Average blur of aligned codes {:.1f}".format(1/precision),file=metrics_file)
    print ("Precision: {:.1%}".format(precision),file=metrics_file)
    metrics_file.close()

# Here the main program - Adapt the work directory to your environment

os.chdir(str(Path.home())+"/Documents/NUVA")
get_nuva(get_nuva_version())
split_nuva()
#refturtle_to_map("CVX")
#shutil.copyfile("nuva_refcode_CVX.csv","nuva_code_CVX.csv")
#map_to_turtle("CVX")
eval_code("CVX",False) # Assess CVX against generic NUVA codes
eval_code("CVX",True)  # Assess CVX against all NUVA codes
#eval_code("ATC",False)
#eval_code("CIS",True)
#eval_code("CVC", False)
#eval_code("SNOMED-CT", True)

