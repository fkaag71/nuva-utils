from rdflib import *
from urllib.request import urlopen,urlretrieve
from pathlib import Path
import csv
import json
import os
import shutil
import math

BaseURI="http://ivci.org/NUVA#"
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
      f2.write(line.replace("http://data.esante.gouv.fr/NUVA","http://ivci.org/NUVA"))
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
    NUVA = Namespace("http://ivci.org/NUVA#") 
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
        writer.writerow([o.rsplit('#')[1],s.rsplit('#')[1],label])
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
            
def eval_code(code):
    rev_fname = "nuva_reverse_"+code+".csv"
    best_fname="nuva_best_"+code+"..csv"

    print ("Loading core graph")
    g = Graph(store="Oxigraph")
    g.parse(core_fname)
    print ("Loading code graph")
    g.parse("nuva_code_"+code+".ttl")

    print ("Retrieve the list of NUVA codes")
    q1="""
    SELECT ?vacnot ?label WHERE {
      ?vac rdfs:subClassOf nuva:Vaccine .
      ?vac skos:notation ?vacnot .
      ?vac rdfs:label ?label filter(lang(?label)='en'||lang(?label)='')
    }
    """
    res1 = g.query(q1)
    
    bestcodes = {}

    for row in res1:
        bestcodes[str(row.vacnot)] = {'label':str(row.label),'count':10000,'code':"None"}
        
    nbnuva = len(bestcodes)

    print ("Retrieve all exact matches")
    q2="""
   SELECT ?extnot ?abstract ?rlabel ?rnot WHERE { 
   ?extcode rdfs:subClassOf nuva:"""+code+""" .
   ?extcode skos:notation ?extnot .
   ?rvac rdfs:subClassOf nuva:Vaccine . 
   ?rvac skos:exactMatch ?extcode .
   ?rvac rdfs:label ?rlabel .
   ?rvac skos:notation ?rnot .
   ?rvac nuvs:isAbstract ?abstract
   } 
   """
    res2 = g.query(q2)

    rev_file = open(rev_fname,'w',encoding="utf-8",newline='')
    rev_writer = csv.writer(rev_file, delimiter=';')
    rev_writer.writerow([code,"Label","Count","NUVA codes"])
    for row in res2:
         if (not row.abstract): rev_writer.writerow([row.extnot,row.rlabel,1,row.rnot])
         bestcodes[str(row.rnot)]['count']=1
         bestcodes[str(row.rnot)]['code']=row.extnot

    print("Retrieve all NUVA codes matching external codes")    
    q3="""
   SELECT ?extnot ?rlabel (count(?codevac) as ?nvac) (GROUP_CONCAT(?vacnot) as ?lvac) WHERE { 
   ?extcode rdfs:subClassOf nuva:"""+code+""" .
   ?extcode skos:notation ?extnot .
   ?rvac rdfs:subClassOf nuva:Vaccine . 
   ?rvac skos:exactMatch ?extcode .
   ?rvac rdfs:label ?rlabel .
   ?rvac nuvs:isAbstract true .
   ?vac rdfs:subClassOf nuva:Vaccine .
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
 } GROUP BY ?extnot ?rlabel
   """
    res3=g.query(q3)

    for row in res3:
         rev_writer.writerow([row.extnot,row.rlabel,row.nvac,row.lvac])
         nuva_codes=row.lvac.split()
         rcount = len(nuva_codes)
     
         for nuva_code in nuva_codes:
            if bestcodes[nuva_code]['count'] >= rcount:
                bestcodes[nuva_code]['count'] = rcount
                bestcodes[nuva_code]['code']=row.extnot
    
    rev_file.close     
    
    print ("Create best codes report "+best_fname)
    best_file = open(best_fname,'w',encoding="utf-8",newline='')
    best_writer = csv.writer(best_file, delimiter=';')
    best_writer.writerow(["NUVA","Label","Best "+code,"Count"])
    unmapped = 0
    totalcount = 0
    for nuvacode in bestcodes:
        best_writer.writerow([nuvacode,bestcodes[nuvacode]['label'],":"+str(bestcodes[nuvacode]['code']),bestcodes[nuvacode]['count']])
        if bestcodes[nuvacode]['code'] == "None" :
            unmapped +=1
        else:
            totalcount = totalcount + bestcodes[nuvacode]['count']

    best_file.close
    
    return ({'Completeness': (nbnuva-unmapped)/nbnuva , 'Precision': math.sqrt((nbnuva-unmapped)/totalcount) })

# Here the main program - Adapt the work directory to your environment

os.chdir(str(Path.home())+"/Documents/NUVA")
get_nuva(get_nuva_version())
split_nuva()
#lang_table("fr","de")
refturtle_to_map("CVX")
shutil.copyfile("nuva_refcode_CVX.csv","nuva_code_CVX.csv")
map_to_turtle("CVX")

q = """ 
   # All vaccines against smallpox
    SELECT ?vcode ?vl WHERE { 
    ?dis rdfs:subClassOf nuva:Disease .
    ?dis rdfs:label "Smallpox-Monkeypox"@en .
    ?vac rdfs:subClassOf nuva:Vaccine .
    ?vac rdfs:label ?vl . 
    ?vac skos:notation ?vcode .
    ?vac nuvs:containsValence ?val . 
    ?val nuvs:prevents ?dis 
 }
"""
#res = query_core(q)
#for row in res:
#     print (f"{row.vcode} - {row.vl}")

res = eval_code("CVX")
print ("Completeness {:.1%} ".format(res['Completeness']))
print ("Precision {:.1%} ".format(res['Precision']))



 
