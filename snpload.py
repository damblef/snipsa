import re
import zipfile
import gzip
from shutil import copyfile
import shutil

vcf_verbose = True

#fname: filename
#crs: chromosomes to read
def load(fname, crs=[], vcf_sample='', force_build=0):
    snpset = {}
    meta = {}
    vcf_idx = 0
    try:
        tmpfile = preprocess_file(fname)
        (build, fmt) = detect_file_format(tmpfile)
        if fmt == 'vcf':
            idxs = get_vcf_sample_idx(tmpfile, vcf_sample)
            #print(idxs)
            if len(idxs) > 0:
                vcf_idx = idxs[0]
            if vcf_verbose:
                print('VCF sample idx:', vcf_idx)
    except:
        print("FORMAT AUTODETECT FAILED!!!!!")
        meta['build'] = 0
        meta['format'] = ''
        meta['total'] = 0
        return (snpset, meta)

    if force_build:
        build = force_build
    meta['build'] = build
    meta['format'] = fmt
    meta['total'] = 0
    
    if fmt == '23andme':
        importer = import_line_23andme
    elif fmt == 'ancestry':
        importer = import_line_ancestry
    elif fmt == 'ftdna':
        importer = import_line_ftdna
    elif fmt == 'myheritage':
        importer = import_line_ftdna #same
    elif fmt == 'vcf':
        importer = import_line_vcf
    else:
        print("Undetected format: build%d, %s"%(build, fmt))
        meta['total'] = 0
        return (snpset, meta)
    
    n_total = 0
    try:
        with open(tmpfile) as f:
            for line in f:
                try:
                    (snp, pos, cr, gen) = importer(line, build, vcf_idx)
                except RuntimeError:
                    continue
                
                if gen[0] == "-":
                    continue
                if cr == "0":
                    continue
                if cr == "YAUTO":
                    cr = "XY"   #???
                if cr == "Y":
                    if len(gen) > 1:
                        snp['gen'] = gen[0]
                if cr == "MT":
                    if len(gen) > 1:
                        snp['gen'] = gen[0]
                
                snp['gen'] = ''.join(sorted(snp['gen']))

                if cr in crs or len(crs) == 0:
                    if cr not in snpset:
                        snpset[cr] = {}
                    #if pos in snpset[cr]:
                    #    if not snp['id'].startswith("i"):
                    #        #print("dup ", snpset[cr][pos], snp)
                    #        pass
                    snpset[cr][pos]=snp
                    n_total+=1
                    continue
    except UnicodeDecodeError:
        return (snpset, meta)

    if build != 36 and build != 37 and build != 38:
        print("BUILD NOT SUPPPORTED!!!!! = %d"%build)
        
    meta['total'] = n_total
    return (snpset, meta)

def import_line_23andme(line, build, idx):
    if len(line) < 7:
        raise RuntimeError()
    if line.startswith('#'):
        raise RuntimeError()
    sline = line.split()
    if len(sline) < 4:
        raise RuntimeError()
    cr = sline[1];
    pos = sline[2];
    gen = sline[3];
        
    snp = {'id': sline[0],
        'cr': cr,
        'gen': gen }

    if build == 36:
        snp['b36'] = pos
    elif build == 37:
        snp['b37'] = pos
    elif build == 38:
        snp['b38'] = pos
        
    return (snp, pos, cr, gen)

def import_line_ancestry(line, build, idx):
    if 'allele1' in line and 'allele2' in line:
        raise RuntimeError()
    if len(line) < 7:
        raise RuntimeError()
    if line.startswith('#'):
        raise RuntimeError()
    sline = line.split()
    if len(sline) < 4:
        raise RuntimeError()
    cr = sline[1];
    if cr == '23':
        cr = 'X'
    elif cr == '24':
        cr = 'Y'
    elif cr == '25':
        cr = 'YAUTO'
    elif cr == '26':
        cr = 'MT'

    pos = sline[2];
    gen = sline[3]+sline[4];
        
    snp = {'id': sline[0],
        'cr': cr,
        'gen': gen }

    if build == 36:
        snp['b36'] = pos
    elif build == 37:
        snp['b37'] = pos
    elif build == 38:
        snp['b38'] = pos
        
    return (snp, pos, cr, gen)

def import_line_ftdna(line, build, idx):
    if len(line) < 7:
        raise RuntimeError()
    if line.startswith('#'):
        raise RuntimeError()
    if line.startswith('RSID'):
        raise RuntimeError()
    sline = line.split(',')
    if len(sline) < 4:
        raise RuntimeError()
    cr = sline[1].strip('"');
    pos = sline[2].strip('"');
    gen = sline[3].strip().strip('"');
        
    snp = {'id': sline[0].strip('"'),
        'cr': cr,
        'gen': gen }

    if build == 36:
        snp['b36'] = pos
    elif build == 37:
        snp['b37'] = pos
    elif build == 38:
        snp['b38'] = pos
        
    return (snp, pos, cr, gen)

def import_line_vcf(line, build, idx):
    if len(line) < 7:
        raise RuntimeError()
    if line.startswith('#'):
        raise RuntimeError()
    sline = line.split()
    if len(sline) < 4:
        raise RuntimeError()
    cr = sline[0];
    if cr == 'chrY':
        cr = 'Y'
    elif cr == 'chrMT':
        cr = 'MT'
    elif cr == 'M':
        cr = 'MT'
    elif cr == 'chrM':
        cr = 'MT'
    else:
        cr.replace('chr','')

    pos = sline[1]
    ref = sline[3]
    alt = sline[4]
    alls = [ref]
    alls+=alt.split(',')

    #skip indel
    if len(ref) > 1 or len(alt) > 1:
        raise RuntimeError()

    #GT index from format string
    form = sline[8]
    gti=0
    for i,gtstr in enumerate(form.split(':')):
        if gtstr == 'GT':
            gti=i

    s = sline[9+idx].split(':')

    #print(pos, alls, gti, s)
    if s[gti][0] == '.':
        raise RuntimeError()
    g = alls[int(s[gti][0])]

    #print(pos, alls, g)
    gen = g+g;

    snp = {'id': sline[2],
        'cr': cr,
        'gen': gen }

    if build == 36:
        snp['b36'] = pos
    elif build == 37:
        snp['b37'] = pos
    elif build == 38:
        snp['b38'] = pos

    return (snp, pos, cr, gen)

def get_vcf_sample_idx(fname, sname):
    lc=0
    idxs=[]
    with open(fname) as f:
        for line in f:
            #print(line)
            if line.startswith('#CHROM'):
                samples=''
                for i, sam in enumerate(line.split('\t')[9:]):
                    if re.search(sname, sam):
                        idxs.append(i)
                    samples+=sam+' '
                if vcf_verbose:
                    print('VCF samples:', samples)
                break
            lc+=1
            if lc > 10000:
                break
    return idxs

def detect_file_format(fname):
    lc=0
    build=0
    fmt=''
    with open(fname) as f:
        for line in f:
            lc += 1
            if lc > 4000:
                break
            if fmt != '' and build != 0:
                break
            if line.startswith('#'):
                if fmt != 'vcf' and 'build ' in line:
                    build = int(re.findall(r'build \d+', line)[0].split()[1])
                if fmt != 'vcf' and 'Build: ' in line:
                    build = int(re.findall(r'Build: \d+', line)[0].split()[1])
                if "23andMe" in line:
                    fmt = '23andme'
                if "AncestryDNA" in line:
                    fmt = 'ancestry'
                if "MyHeritage" in line:
                    fmt = 'myheritage'
                if "##fileformat=VCF" in line:
                    fmt = 'vcf'
                if "##reference" in line:
                    #hacky autodetect may work for many files
                    if '37' in line:
                        build = 37
                    if '38' in line:
                        build = 38
                continue
            if lc == 1 and line.startswith('RSID'):
                     fmt = 'ftdna'
            #autodetect build by some rs ids if needed
            if build == 0:
                sline=line.split(',')
                if sline[0].strip('"') == 'rs6681049' and  sline[2].strip('"') == '800007':
                    build = 37
                if sline[0].strip('"') == 'rs6681049' and  sline[2].strip('"') == '789870':
                    build = 36
            if build == 0:
                sline=line.split(',')
                if sline[0].strip('"') == 'rs3131972' and  sline[2].strip('"') == '752721':
                    build = 37
                if sline[0].strip('"') == 'rs3131972' and  sline[2].strip('"') == '742584':
                    build = 36
            if build == 0:
                sline=line.split(',')
                if sline[0].strip('"') == 'rs3934834' and  sline[2].strip('"') == '1005806':
                    build = 37
                if sline[0].strip('"') == 'rs3934834' and  sline[2].strip('"') == '995669':
                    build = 36
            if build == 0:
                sline=line.split(',')
                if sline[0].strip('"') == 'rs11260549' and  sline[2].strip('"') == '1121794':
                    build = 37
                if sline[0].strip('"') == 'rs11260549' and  sline[2].strip('"') == '1111657':
                    build = 36
    #print("Detected format: build%d, %s"%(build, fmt))
    return (build, fmt)

def is_gz_file(fname):
    with open(fname, 'rb') as f:
        return f.read(2) == b'\x1f\x8b'

def preprocess_file(fname):
    #TODO make real temp file
    tmpfile = 'genome_data.tmp'
    if zipfile.is_zipfile(fname):
        with zipfile.ZipFile(fname) as z:
            zfname = z.namelist()[0]
            #print('ZIP input file: %s'%zfname)
            with z.open(zfname) as zf, open(tmpfile, 'wb') as f:
                shutil.copyfileobj(zf, f)
                
    elif is_gz_file(fname):
        #print('gzip input file: %s'%fname)
        with gzip.open(fname, 'rb') as f_in:
            with open(tmpfile, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        #print('ASCII input file: %s'%fname)
        shutil.copyfile(fname, tmpfile);
    return tmpfile

def save(fname, snpset, build=37):
    b3x='b%d'%build
    with open(fname, 'w') as f:
        print('# This data file generated by Snipsa, not by 23andMe', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# We are using reference human assembly build %d '%build, file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# More information on reference human assembly build %d '%build, file = f)
        print('# ', file = f)
        print('# ', file = f)
        print('# rsid	chromosome	position	genotype', file = f)
        for cr in snpset:
            for i in snpset[cr]:
                snp = snpset[cr][i]
                if  snp[b3x] == '0':
                    print('TODO:', snp)
                    continue
                if len(snp['gen']) == 1:
                    snp['gen'] += snp['gen']
                row = '%s\t%s\t%s\t%s'%(snp['id'], cr, snp[b3x], snp['gen'])
                print(row, file = f)

def index_by_rs(snpset):
    snpseto = {}

    for cr in snpset:
        if cr not in snpseto:
            snpseto[cr] = {}
        for snp in snpset[cr]:
            snpseto[cr][ snpset[cr][snp]['id'] ] = snpset[cr][snp]
    return snpseto



def show_stats(snpset):
    n_total = 0

    for cr in snpset:
        n_smps = len(snpset[cr])
        print("Chromosome %s: %s SNPs"%(cr, n_smps))
        n_total += n_smps
    print("Total SNPs: %d"%n_total)

def allele_sort_key(al):
    if len(al) == 1:
        key = list('_'+al)
    else:
        key = list(al)

    if key[0] == 'D':
        key[0] = 'U'
    if key[0] == 'I':
        key[0] = 'V'
    if key[1] == 'D':
        key[1] = 'U'
    if key[1] == 'I':
        key[1] = 'V'
    return ''.join(key)

def show_gts(snpset):
    d={}
    for cr in snpset:
        for snp in snpset[cr]:
            gt = snpset[cr][snp]['gen']
            if gt not in d:
                d[gt] = 1
            else:
                d[gt] += 1
            
    #print(d)
    print("Total alleles found:")
    for al in sorted(d, key=allele_sort_key):
        print("%s: %d"%(al, d[al]))


