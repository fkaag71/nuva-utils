from rdflib import *
from urllib.request import urlopen,urlretrieve
from pathlib import Path
import csv
import json
import os
import shutil

BaseURI="http://ivci.org/NUVA#"
full_fname="nuva_ivci.rdf"
core_fname = "nuva_core.ttl"

def get_nuva_version():
    url="https://ans.mesvaccins.net/last_version.json"
    response=urlopen(url)
    data_json=json.loads(response.read())
    return (data_json['version'])

def get_nuva(version):
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
    g = Graph()
    g.parse(full_fname)

    CodesParent=URIRef(BaseURI+"Code")
    graph_codes = {}
    graph_langs = {}

    Codes = g.subjects(RDFS.subClassOf,CodesParent)
    for Code in Codes:
        label=g.value(Code,RDFS.label)
        graph_codes[label] = Graph()

    g_core= Graph()

    for s,p,o in g:

        # Extract languages
        if (o.__class__.__name__== "Literal"):
            lang = o.language
            if (lang!="en" and lang!=None): 
                if (not lang in graph_langs.keys()):
                    graph_langs[lang] = Graph();
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
    g = Graph()
    g_core = Graph()

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
        g = Graph()
        g_core=Graph()
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
    g_core = Graph()
    g_core.parse(core_fname)
    return g_core.query(q)

def query_code(q,code):
    g = Graph()
    g.parse(core_fname)
    g.parse("nuva_code_"+code+".ttl")
    return g.query(q)


# Here the main program - Adapt the work directory to your environment

os.chdir(str(Path.home())+"/Documents/NUVA")
# get_nuva(get_nuva_version())
# split_nuva()
# refturtle_to_map("CVX")
# shutil.copyfile("nuva_refcode_CVX.csv","nuva_code_CVX.csv")
# map_to_turtle("CVX")

q1 = """ 
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
#res = query_core(q1)
#for row in res:
#    print (str(row[0])+"-"+str(row[1]))

q2="""
    # List CVX Codes
    SELECT ?cvx ?nuva ?lvac WHERE { 
    ?vac rdfs:subClassOf nuva:Vaccine . 
    ?vac skos:notation ?nuva .
    ?vac skos:exactMatch ?code .
    ?code rdfs:subClassOf nuva:CVX .
    ?code skos:notation ?cvx .
    ?vac rdfs:label $lvac
    }
"""
res=query_code(q2,"CVX")
for row in res:
    print ("CVX "+str(row[0])+" = "+str(row[1])+" : "+str(row[2]))
 
