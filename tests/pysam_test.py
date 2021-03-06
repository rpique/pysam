#!/usr/bin/env python
'''unit testing code for pysam.

Execute in the :file:`tests` directory as it requires the Makefile
and data files located there.
'''

import pysam
import unittest
import os, re, sys
import itertools
import collections
import subprocess
import shutil
import logging

IS_PYTHON3 = sys.version_info[0] >= 3

if IS_PYTHON3:
    from itertools import zip_longest
else:
    from itertools import izip as zip_longest


SAMTOOLS="samtools"
WORKDIR="pysam_test_work"
DATADIR="pysam_data"

def checkBinaryEqual( filename1, filename2 ):
    '''return true if the two files are binary equal.'''
    if os.path.getsize( filename1 ) !=  os.path.getsize( filename2 ):
        return False

    infile1 = open(filename1, "rb")
    infile2 = open(filename2, "rb")

    def chariter( infile ):
        while 1:
            c = infile.read(1)
            if c == b"": break
            yield c

    found = False
    for c1,c2 in zip_longest( chariter( infile1), chariter( infile2) ):
        if c1 != c2: break
    else:
        found = True

    infile1.close()
    infile2.close()
    return found

def runSamtools( cmd ):
    '''run a samtools command'''

    try:
        retcode = subprocess.call(cmd, shell=True,
                                  stderr = subprocess.PIPE)
        if retcode < 0:
            print("Child was terminated by signal", -retcode)
    except OSError as e:
        print("Execution failed:", e)

def getSamtoolsVersion():
    '''return samtools version'''

    with subprocess.Popen(SAMTOOLS, shell=True, stderr=subprocess.PIPE).stderr as pipe:
        lines = b"".join(pipe.readlines())

    if IS_PYTHON3:
        lines = lines.decode('ascii')
    return re.search( "Version:\s+(\S+)", lines).groups()[0]

class BinaryTest(unittest.TestCase):
    '''test samtools command line commands and compare
    against pysam commands.

    Tests fail, if the output is not binary identical.
    '''

    first_time = True

    # a dictionary of commands to test
    # first entry: (samtools output file, samtools command)
    # second entry: (pysam output file, (pysam function, pysam options) )
    commands = \
        { 
          "view" :
              (
                ("ex1.view", "view ex1.bam > ex1.view"),
                ("pysam_ex1.view", (pysam.view, "ex1.bam" ) ),
                ),
          "view2" :
              (
                ("ex1.view", "view -bT ex1.fa -o ex1.view2 ex1.sam"),
                # note that -o ex1.view2 throws exception.
                ("pysam_ex1.view", (pysam.view, "-bT ex1.fa -oex1.view2 ex1.sam" ) ),
                ),
          "sort" :
              (
                ( "ex1.sort.bam", "sort ex1.bam ex1.sort" ),
                ( "pysam_ex1.sort.bam", (pysam.sort, "ex1.bam pysam_ex1.sort" ) ),
                ),
          "mpileup" :
              (
                ("ex1.pileup", "mpileup ex1.bam > ex1.pileup" ),
                ("pysam_ex1.mpileup", (pysam.mpileup, "ex1.bam" ) ),
                ),
          "depth" :
              (
                ("ex1.depth", "depth ex1.bam > ex1.depth" ),
                ("pysam_ex1.depth", (pysam.depth, "ex1.bam" ) ),
                ),
          "faidx" : 
              ( 
                ("ex1.fa.fai", "faidx ex1.fa"), 
                ("pysam_ex1.fa.fai", (pysam.faidx, "ex1.fa") ),
                ),
          "index":
              (
                ("ex1.bam.bai", "index ex1.bam" ),
                ("pysam_ex1.bam.bai", (pysam.index, "pysam_ex1.bam" ) ),
                ),
          "idxstats" :
              ( 
                ("ex1.idxstats", "idxstats ex1.bam > ex1.idxstats" ),
                ("pysam_ex1.idxstats", (pysam.idxstats, "pysam_ex1.bam" ) ),
                ),
          "fixmate" :
              (
                ("ex1.fixmate", "fixmate ex1.bam ex1.fixmate" ),
                ("pysam_ex1.fixmate", (pysam.fixmate, "pysam_ex1.bam pysam_ex1.fixmate") ),
                ),
          "flagstat" :
              (
                ("ex1.flagstat", "flagstat ex1.bam > ex1.flagstat" ),
                ("pysam_ex1.flagstat", (pysam.flagstat, "pysam_ex1.bam") ),
                ),
          "calmd" :
              (
                ("ex1.calmd", "calmd ex1.bam ex1.fa > ex1.calmd" ),
                ("pysam_ex1.calmd", (pysam.calmd, "pysam_ex1.bam ex1.fa") ),
                ),
          "merge" :
              (
                ("ex1.merge", "merge -f ex1.merge ex1.bam ex1.bam" ),
                # -f option does not work - following command will cause the subsequent
                # command to fail
                ("pysam_ex1.merge", (pysam.merge, "pysam_ex1.merge pysam_ex1.bam pysam_ex1.bam") ),
                ),
          "rmdup" :
              (
                ("ex1.rmdup", "rmdup ex1.bam ex1.rmdup" ),
                ("pysam_ex1.rmdup", (pysam.rmdup, "pysam_ex1.bam pysam_ex1.rmdup" )),
                ),
          "reheader" :
              (
                ( "ex1.reheader", "reheader ex1.bam ex1.bam > ex1.reheader"),
                ( "pysam_ex1.reheader", (pysam.reheader, "ex1.bam ex1.bam" ) ),
                ),
          "cat":
              (
                ( "ex1.cat", "cat ex1.bam ex1.bam > ex1.cat"),
                ( "pysam_ex1.cat", (pysam.cat, "ex1.bam ex1.bam" ) ),
                ),
          "targetcut":
              (
                ("ex1.targetcut", "targetcut ex1.bam > ex1.targetcut" ),
                ("pysam_ex1.targetcut", (pysam.targetcut, "pysam_ex1.bam") ),
                ),
          "phase":
              (
                ("ex1.phase", "phase ex1.bam > ex1.phase" ),
                ("pysam_ex1.phase", (pysam.phase, "pysam_ex1.bam") ),
                ),
          "import" :
              (
                ("ex1.bam", "import ex1.fa.fai ex1.sam.gz ex1.bam" ),
                ("pysam_ex1.bam", (pysam.samimport, "ex1.fa.fai ex1.sam.gz pysam_ex1.bam") ),
                ),
          "bam2fq":
              (
                ("ex1.bam2fq", "bam2fq ex1.bam > ex1.bam2fq" ),
                ("pysam_ex1.bam2fq", (pysam.bam2fq, "pysam_ex1.bam") ),
                ),
          "pad2unpad":
              (
                ("ex2.unpad", "pad2unpad -T ex1.fa ex2.bam > ex2.unpad" ),
                ("pysam_ex2.unpad", (pysam.pad2unpad, "-T ex1.fa ex2.bam") ),
                ),
          "bamshuf":
              (
                ("ex1.bamshuf.bam", "bamshuf ex1.bam ex1.bamshuf" ),
                ("pysam_ex1.bamshuf.bam", (pysam.bamshuf, "ex1.bam pysam_ex1.bamshuf") ),
                ),
          "bedcov":
              (
                ("ex1.bedcov", "bedcov ex1.bed ex1.bam > ex1.bedcov" ),
                ("pysam_ex1.bedcov", (pysam.bedcov, "ex1.bed ex1.bam") ),
                ),
        }

    # some tests depend on others. The order specifies in which order
    # the samtools commands are executed.
    # The first three (faidx, import, index) need to be in that order, 
    # the rest is arbitrary.
    order = ('faidx', 'import', 'index', 
             # 'pileup1', 'pileup2', deprecated
             # 'glfview', deprecated
             'view', 'view2',
             'sort',
             'mpileup',
             'depth',
             'idxstats',
             'fixmate',
             'flagstat',
             ## 'calmd',
             'merge',
             'rmdup',
             'reheader',
             'cat',
             'bedcov',
             'targetcut',
             'phase',
             'bamshuf',
             'bam2fq',
             'pad2unpad',
              )

    def setUp( self ):
        '''setup tests. 

        For setup, all commands will be run before the first test is
        executed. Individual tests will then just compare the output
        files.
        '''
        if BinaryTest.first_time:

            # remove previous files
            if os.path.exists( WORKDIR ):
                shutil.rmtree( WORKDIR )
                pass

            # copy the source files to WORKDIR
            os.makedirs( WORKDIR )

            shutil.copy(os.path.join(DATADIR,"ex1.fa"), 
                        os.path.join(WORKDIR, "pysam_ex1.fa"))
            shutil.copy(os.path.join(DATADIR,"ex1.fa"),
                        os.path.join( WORKDIR, "ex1.fa"))
            shutil.copy(os.path.join(DATADIR,"ex1.sam.gz"),
                        os.path.join(WORKDIR, "ex1.sam.gz"))
            shutil.copy(os.path.join(DATADIR,"ex1.sam"),
                        os.path.join( WORKDIR, "ex1.sam"))
            shutil.copy(os.path.join(DATADIR,"ex2.bam"),
                        os.path.join( WORKDIR, "ex2.bam"))

            # cd to workdir
            savedir = os.getcwd()
            os.chdir( WORKDIR )
            
            for label in self.order:
                # print ("command=", label)
                command = self.commands[label]
                # build samtools command and target and run
                samtools_target, samtools_command = command[0]
                runSamtools( " ".join( (SAMTOOLS, samtools_command )))

                # get pysam command and run
                try:
                    pysam_target, pysam_command = command[1]
                except ValueError as msg:
                    raise ValueError( "error while setting up %s=%s: %s" %\
                                      (label, command, msg) )

                pysam_method, pysam_options = pysam_command

                try:
                    output = pysam_method( *pysam_options.split(" "), raw=True)
                except pysam.SamtoolsError as msg:
                    raise pysam.SamtoolsError( "error while executing %s: options=%s: msg=%s" %\
                                                   (label, pysam_options, msg) )

                
                if ">" in samtools_command:
                    with open( pysam_target, "wb" ) as outfile:
                        if type(output) == list:
                            if IS_PYTHON3:
                                for line in output: 
                                    outfile.write( line.encode('ascii') )
                            else:
                                for line in output: outfile.write( line )
                        else:
                            outfile.write(output)

            os.chdir( savedir )
            BinaryTest.first_time = False

        samtools_version = getSamtoolsVersion()

        
        def _r( s ):
            # patch - remove any of the alpha/beta suffixes, i.e., 0.1.12a -> 0.1.12
            if s.count('-') > 0: s = s[0:s.find('-')]
            return re.sub( "[^0-9.]", "", s )

        if _r(samtools_version) != _r( pysam.__samtools_version__):
            raise ValueError("versions of pysam/samtools and samtools differ: %s != %s" % \
                                 (pysam.__samtools_version__,
                                  samtools_version ))

    def checkCommand( self, command ):
        if command:
            samtools_target, pysam_target = self.commands[command][0][0], self.commands[command][1][0]
            samtools_target = os.path.join( WORKDIR, samtools_target )
            pysam_target = os.path.join( WORKDIR, pysam_target )
            self.assertTrue( checkBinaryEqual( samtools_target, pysam_target ), 
                             "%s failed: files %s and %s are not the same" % (command, samtools_target, pysam_target) )
            
    def testImport( self ):
        self.checkCommand( "import" )

    def testIndex( self ):
        self.checkCommand( "index" )

    def testSort( self ):
        self.checkCommand( "sort" )

    def testMpileup( self ):
        self.checkCommand( "mpileup" )

    def testDepth( self ):
        self.checkCommand( "depth" )

    def testIdxstats( self ):
        self.checkCommand( "idxstats" )

    def testFixmate( self ):
        self.checkCommand( "fixmate" )

    def testFlagstat( self ):
        self.checkCommand( "flagstat" )
        
    def testMerge( self ):
        self.checkCommand( "merge" )

    def testRmdup( self ):
        self.checkCommand( "rmdup" )

    def testReheader( self ):
        self.checkCommand( "reheader" )

    def testCat( self ):
        self.checkCommand( "cat" )

    def testTargetcut( self ):
        self.checkCommand( "targetcut" )

    def testPhase( self ):
        self.checkCommand( "phase" )

    def testBam2fq( self ):
        self.checkCommand( "bam2fq" )

    def testBedcov( self ):
        self.checkCommand( "bedcov" )

    def testBamshuf( self ):
        self.checkCommand( "bamshuf" )

    def testPad2Unpad( self ):
        self.checkCommand( "pad2unpad" )

    # def testPileup1( self ):
    #     self.checkCommand( "pileup1" )
    
    # def testPileup2( self ):
    #     self.checkCommand( "pileup2" )

    # deprecated
    # def testGLFView( self ):
    #     self.checkCommand( "glfview" )

    def testView( self ):
        self.checkCommand( "view" )

    def testEmptyIndex( self ):
        self.assertRaises( IOError, pysam.index, "exdoesntexist.bam" )

    def __del__(self):
        if os.path.exists( WORKDIR ):
            pass
        # shutil.rmtree( WORKDIR )

class IOTest(unittest.TestCase):
    '''check if reading samfile and writing a samfile are consistent.'''

    def checkEcho( self, 
                   input_filename, 
                   reference_filename, 
                   output_filename, 
                   input_mode, output_mode, use_template = True ):
        '''iterate through *input_filename* writing to *output_filename* and
        comparing the output to *reference_filename*. 
        
        The files are opened according to the *input_mode* and *output_mode*.

        If *use_template* is set, the header is copied from infile using the
        template mechanism, otherwise target names and lengths are passed 
        explicitely. 

        '''

        infile = pysam.Samfile(os.path.join(DATADIR,input_filename),
                               input_mode )
        if use_template:
            outfile = pysam.Samfile(output_filename, 
                                    output_mode, 
                                    template=infile)
        else:
            outfile = pysam.Samfile(output_filename, 
                                    output_mode, 
                                    referencenames = infile.references,
                                    referencelengths = infile.lengths,
                                    add_sq_text = False)
            
        iter = infile.fetch()

        for x in iter: outfile.write( x )
        infile.close()
        outfile.close()

        self.assertTrue(
            checkBinaryEqual(os.path.join(DATADIR, reference_filename),
                             output_filename), 
            "files %s and %s are not the same" % (reference_filename,
                                                  output_filename))


    def testReadWriteBam( self ):
        
        input_filename = "ex1.bam"
        output_filename = "pysam_ex1.bam"
        reference_filename = "ex1.bam"

        self.checkEcho( input_filename, reference_filename, output_filename,
                        "rb", "wb" )

    def testReadWriteBamWithTargetNames( self ):
        
        input_filename = "ex1.bam"
        output_filename = "pysam_ex1.bam"
        reference_filename = "ex1.bam"

        self.checkEcho( input_filename, reference_filename, output_filename,
                        "rb", "wb", use_template = False )

    def testReadWriteSamWithHeader( self ):
        
        input_filename = "ex2.sam"
        output_filename = "pysam_ex2.sam"
        reference_filename = "ex2.sam"

        self.checkEcho( input_filename, reference_filename, output_filename,
                        "r", "wh" )

    def testReadWriteSamWithoutHeader( self ):
        
        input_filename = "ex2.sam"
        output_filename = "pysam_ex2.sam"
        reference_filename = "ex1.sam"

        self.checkEcho( input_filename, reference_filename, output_filename,
                        "r", "w" )

    def testReadSamWithoutTargetNames( self ):
        '''see issue 104.'''
        input_filename = os.path.join(DATADIR,
                                      "example_unmapped_reads_no_sq.sam")

        # raise exception in default mode
        self.assertRaises( ValueError, pysam.Samfile, input_filename, "r" )

        # raise exception if no SQ files
        self.assertRaises( ValueError, pysam.Samfile, input_filename, "r",
                           check_header = True)

        infile = pysam.Samfile( input_filename, check_header = False, check_sq = False )
        result = list(infile.fetch())

    def testReadBamWithoutTargetNames( self ):
        '''see issue 104.'''
        input_filename = os.path.join(DATADIR,"example_unmapped_reads_no_sq.bam")

        # raise exception in default mode
        self.assertRaises( ValueError, pysam.Samfile, input_filename, "r" )

        # raise exception if no SQ files
        self.assertRaises( ValueError, pysam.Samfile, input_filename, "r",
                           check_header = True)


        infile = pysam.Samfile( input_filename, check_header = False, check_sq = False )
        result = list(infile.fetch( until_eof = True))

    def testReadSamWithoutHeader( self ):
        input_filename = os.path.join(DATADIR,"ex1.sam")

        # reading from a samfile without header is not implemented.
        self.assertRaises( ValueError,
                           pysam.Samfile,
                           input_filename, 
                           "r" )

        self.assertRaises( ValueError,
                           pysam.Samfile,
                           input_filename,
                           "r",
                           check_header = False )

    def testReadUnformattedFile( self ):
        '''test reading from a file that is not bam/sam formatted'''
        input_filename = os.path.join(DATADIR,'Makefile')

        # bam - file raise error
        self.assertRaises( ValueError, 
                           pysam.Samfile, 
                           input_filename, 
                           "rb" )

        # sam - file error, but can't fetch
        self.assertRaises( ValueError, 
                           pysam.Samfile,
                           input_filename, 
                           "r" )
        
        self.assertRaises( ValueError, 
                           pysam.Samfile, 
                           input_filename, 
                           "r", 
                           check_header = False)

    def testBAMWithoutAlignedReads( self ):
        '''see issue 117'''
        input_filename = os.path.join(DATADIR,"test_unaligned.bam")
        samfile = pysam.Samfile( input_filename, "rb", check_sq = False )
        samfile.fetch( until_eof = True )

    def testBAMWithShortBAI( self ):
        '''see issue 116'''
        input_filename = os.path.join(DATADIR,"example_bai.bam")
        samfile = pysam.Samfile( input_filename, "rb", check_sq = False )
        samfile.fetch( 'chr2' )

    def testFetchFromClosedFile( self ):

        samfile = pysam.Samfile( os.path.join(DATADIR,"ex1.bam"),
                                 "rb")
        samfile.close()
        self.assertRaises( ValueError, samfile.fetch, 'chr1', 100, 120)

    def testClosedFile( self ):
        '''test that access to a closed samfile raises ValueError.'''

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex1.bam"), 
                                "rb")
        samfile.close()
        self.assertRaises( ValueError, samfile.fetch, 'chr1', 100, 120)
        self.assertRaises( ValueError, samfile.pileup, 'chr1', 100, 120)
        self.assertRaises( ValueError, samfile.getrname, 0 )
        self.assertRaises( ValueError, samfile.tell )
        self.assertRaises( ValueError, samfile.seek, 0 )
        self.assertRaises( ValueError, getattr, samfile, "nreferences" )
        self.assertRaises( ValueError, getattr, samfile, "references" )
        self.assertRaises( ValueError, getattr, samfile, "lengths" )
        self.assertRaises( ValueError, getattr, samfile, "text" )
        self.assertRaises( ValueError, getattr, samfile, "header" )

        # write on closed file 
        self.assertEqual( 0, samfile.write(None) )

    def testAutoDetection( self ):
        '''test if autodetection works.'''

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex3.sam"))
        self.assertRaises( ValueError, samfile.fetch, 'chr1' )
        samfile.close()

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex3.bam"))
        samfile.fetch('chr1')
        samfile.close()

    def testReadingFromSamFileWithoutHeader( self ):
        '''read from samfile without header.
        '''
        samfile = pysam.Samfile(os.path.join(DATADIR,"ex7.sam"),
                                check_header = False, 
                                check_sq = False)
        self.assertRaises( NotImplementedError, samfile.__iter__ )

    def testReadingFromFileWithoutIndex( self ):
        '''read from bam file without index.'''

        assert not os.path.exists(os.path.join(DATADIR,"ex2.bam.bai"))
        samfile = pysam.Samfile(os.path.join(DATADIR,"ex2.bam"),
                                "rb")
        self.assertRaises( ValueError, samfile.fetch )
        self.assertEqual(len(list(samfile.fetch(until_eof = True))), 
                         3270)

    def testReadingUniversalFileMode( self ):
        '''read from samfile without header.
        '''

        input_filename = "ex2.sam"
        output_filename = "pysam_ex2.sam"
        reference_filename = "ex1.sam"

        self.checkEcho( input_filename, reference_filename, output_filename,
                        "rU", "w" )

class TestFloatTagBug( unittest.TestCase ):
    '''see issue 71'''

    def testFloatTagBug( self ): 
        '''a float tag before another exposed a parsing bug in bam_aux_get.

        Fixed in 0.1.19
        '''
        samfile = pysam.Samfile(os.path.join(DATADIR,"tag_bug.bam"))
        read = next(samfile.fetch(until_eof=True))
        self.assertTrue( ('XC',1) in read.tags )
        self.assertEqual(read.opt('XC'), 1)

class TestLargeFieldBug( unittest.TestCase ):
    '''see issue 100'''

    def testLargeFileBug( self ): 
        '''when creating a read with a large entry in the tag field
        causes an errror:
            NotImplementedError: tags field too large
        '''
        samfile = pysam.Samfile(os.path.join(DATADIR,"issue100.bam"))
        read = next(samfile.fetch(until_eof=True))
        new_read = pysam.AlignedRead()
        new_read.tags = read.tags
        self.assertEqual( new_read.tags, read.tags )

class TestTagParsing( unittest.TestCase ):
    '''tests checking the accuracy of tag setting and retrieval.'''

    def makeRead( self ):
        a = pysam.AlignedRead()
        a.qname = "read_12345"
        a.tid = 0
        a.seq="ACGT" * 3
        a.flag = 0
        a.rname = 0
        a.pos = 1
        a.mapq = 20
        a.cigar = ( (0,10), (2,1), (0,25) )
        a.mrnm = 0
        a.mpos=200
        a.isize = 0
        a.qual ="1234" * 3
        # todo: create tags
        return a

    def testNegativeIntegers( self ):
        x = -2
        aligned_read = self.makeRead()
        aligned_read.tags = [("XD", int(x) ) ]
        # print (aligned_read.tags)

    def testNegativeIntegers2( self ):
        x = -2
        r = self.makeRead()
        r.tags = [("XD", int(x) ) ]
        outfile = pysam.Samfile( "test.bam",
                                 "wb",
                                 referencenames = ("chr1",),
                                 referencelengths = (1000,) )
        outfile.write (r )
        outfile.close()

    def testCigarString( self ):
        r = self.makeRead()
        self.assertEqual( r.cigarstring, "10M1D25M" )
        r.cigarstring = "20M10D20M"
        self.assertEqual( r.cigar, [(0,20), (2,10), (0,20)])

    def testLongTags( self ):
        '''see issue 115'''
        
        r = self.makeRead()
        rg = 'HS2000-899_199.L3'
        tags = [('XC', 85), ('XT', 'M'), ('NM', 5), 
                ('SM', 29), ('AM', 29), ('XM', 1), 
                ('XO', 1), ('XG', 4), ('MD', '37^ACCC29T18'), 
                ('XA','5,+11707,36M1I48M,2;21,-48119779,46M1I38M,2;hs37d5,-10060835,40M1D45M,3;5,+11508,36M1I48M,3;hs37d5,+6743812,36M1I48M,3;19,-59118894,46M1I38M,3;4,-191044002,6M1I78M,3;')]

        r.tags = tags
        r.tags += [("RG",rg)] * 100
        tags += [("RG",rg)] * 100
        
        self.assertEqual( tags, r.tags )

class TestClipping(unittest.TestCase):
    
    def testClipping( self ):
        
        self.samfile = pysam.Samfile(os.path.join(DATADIR,"softclip.bam"),
                                     "rb")
        for read in self.samfile:

            if read.qname == "r001":
                self.assertEqual( read.seq, b'AAAAGATAAGGATA' )
                self.assertEqual( read.query, b'AGATAAGGATA' )
                self.assertEqual( read.qual, None )
                self.assertEqual( read.qqual, None )
                
            elif read.qname == "r002":
                
                self.assertEqual( read.seq, b'GCCTAAGCTAA' )
                self.assertEqual( read.query, b'AGCTAA' )
                self.assertEqual( read.qual, b'01234567890' )
                self.assertEqual( read.qqual, b'567890' )
            
            elif read.qname == "r003":
                
                self.assertEqual( read.seq, b'GCCTAAGCTAA' )
                self.assertEqual( read.query, b'GCCTAA' )
                self.assertEqual( read.qual, b'01234567890' )
                self.assertEqual( read.qqual, b'012345' )

            elif read.qname == "r004":
                
                self.assertEqual( read.seq, b'TAGGC' )
                self.assertEqual( read.query, b'TAGGC' )
                self.assertEqual( read.qual, b'01234' )
                self.assertEqual( read.qqual, b'01234' )
                
class TestIteratorRow(unittest.TestCase):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                   "rb")

    def checkRange( self, rnge ):
        '''compare results from iterator with those from samtools.'''
        ps = list(self.samfile.fetch(region=rnge))
        sa = list(pysam.view( os.path.join(DATADIR,"ex1.bam"),
                              rnge,
                              raw = True) )
        self.assertEqual( len(ps), len(sa), "unequal number of results for range %s: %i != %i" % (rnge, len(ps), len(sa) ))
        # check if the same reads are returned and in the same order
        for line, (a, b) in enumerate( list(zip( ps, sa )) ):
            d = b.split("\t")
            self.assertEqual( a.qname, d[0], "line %i: read id mismatch: %s != %s" % (line, a.rname, d[0]) )
            self.assertEqual( a.pos, int(d[3])-1, "line %i: read position mismatch: %s != %s, \n%s\n%s\n" % \
                                  (line, a.pos, int(d[3])-1,
                                   str(a), str(d) ) )
            if sys.version_info[0] < 3:
                qual = d[10]
            else:
                qual = d[10].encode('ascii')
            self.assertEqual( a.qual, qual, "line %i: quality mismatch: %s != %s, \n%s\n%s\n" % \
                                  (line, a.qual, qual,
                                   str(a), str(d) ) )

    def testIteratePerContig(self):
        '''check random access per contig'''
        for contig in self.samfile.references:
            self.checkRange( contig )

    def testIterateRanges(self):
        '''check random access per range'''
        for contig, length in zip(self.samfile.references, self.samfile.lengths):
            for start in range( 1, length, 90):
                self.checkRange( "%s:%i-%i" % (contig, start, start + 90) ) # this includes empty ranges

    def tearDown(self):
        self.samfile.close()


class TestIteratorRowAll(unittest.TestCase):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                   "rb" )

    def testIterate(self):
        '''compare results from iterator with those from samtools.'''
        ps = list(self.samfile.fetch())
        sa = list(pysam.view(os.path.join(DATADIR,"ex1.bam"),
                             raw = True))
        self.assertEqual( len(ps), len(sa), "unequal number of results: %i != %i" % (len(ps), len(sa) ))
        # check if the same reads are returned
        for line, pair in enumerate( list(zip( ps, sa )) ):
            data = pair[1].split("\t")
            self.assertEqual( pair[0].qname, data[0], "read id mismatch in line %i: %s != %s" % (line, pair[0].rname, data[0]) )

    def tearDown(self):
        self.samfile.close()

class TestIteratorColumn(unittest.TestCase):
    '''test iterator column against contents of ex4.bam.'''
    
    # note that samfile contains 1-based coordinates
    # 1D means deletion with respect to reference sequence
    # 
    mCoverages = { 'chr1' : [ 0 ] * 20 + [1] * 36 + [0] * (100 - 20 -35 ),
                   'chr2' : [ 0 ] * 20 + [1] * 35 + [0] * (100 - 20 -35 ),
                   }

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex4.bam"),
                                   "rb" )

    def checkRange( self, contig, start = None, end = None, truncate = False ):
        '''compare results from iterator with those from samtools.'''
        # check if the same reads are returned and in the same order
        for column in self.samfile.pileup(contig, start, end, truncate = truncate):
            if truncate:
                self.assertGreaterEqual( column.pos, start )
                self.assertLess( column.pos, end )
            thiscov = len(column.pileups)
            refcov = self.mCoverages[self.samfile.getrname(column.tid)][column.pos]
            self.assertEqual( thiscov, refcov, "wrong coverage at pos %s:%i %i should be %i" % (self.samfile.getrname(column.tid), column.pos, thiscov, refcov))

    def testIterateAll(self):
        '''check random access per contig'''
        self.checkRange( None )

    def testIteratePerContig(self):
        '''check random access per contig'''
        for contig in self.samfile.references:
            self.checkRange( contig )

    def testIterateRanges(self):
        '''check random access per range'''
        for contig, length in zip(self.samfile.references, self.samfile.lengths):
            for start in range( 1, length, 90):
                self.checkRange( contig, start, start + 90 ) # this includes empty ranges

    def testInverse( self ):
        '''test the inverse, is point-wise pileup accurate.'''
        for contig, refseq in list(self.mCoverages.items()):
            refcolumns = sum(refseq)
            for pos, refcov in enumerate( refseq ):
                columns = list(self.samfile.pileup( contig, pos, pos+1) )
                if refcov == 0:
                    # if no read, no coverage
                    self.assertEqual( len(columns), refcov, "wrong number of pileup columns returned for position %s:%i, %i should be %i" %(contig,pos,len(columns), refcov) )
                elif refcov == 1:
                    # one read, all columns of the read are returned
                    self.assertEqual( len(columns), refcolumns, "pileup incomplete at position %i: got %i, expected %i " %\
                                          (pos, len(columns), refcolumns))

    def testIterateTruncate( self ):
        '''check random access per range'''
        for contig, length in zip(self.samfile.references, self.samfile.lengths):
            for start in range( 1, length, 90):
                self.checkRange( contig, start, start + 90, truncate = True ) # this includes empty ranges
                
    def tearDown(self):
        self.samfile.close()

class TestIteratorColumn2(unittest.TestCase):
    '''test iterator column against contents of ex1.bam.'''

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                   "rb")

    def testStart( self ):
        #print self.samfile.fetch().next().pos
        #print self.samfile.pileup().next().pos
        pass

    def testTruncate( self ):
        '''see issue 107.'''
        # note that ranges in regions start from 1
        p = self.samfile.pileup(region='chr1:170:172', truncate=True)
        columns = [ x.pos for x in p ]
        self.assertEqual( len(columns), 3)
        self.assertEqual( columns, [169,170,171] )

        p = self.samfile.pileup( 'chr1', 169, 172, truncate=True)
        columns = [ x.pos for x in p ]
    
        self.assertEqual( len(columns), 3)
        self.assertEqual( columns, [169,170,171] )

    def testAccessOnClosedIterator( self ):
        '''see issue 131

        Accessing pileup data after iterator has closed.
        '''
        pcolumn = self.samfile.pileup('chr1', 170, 180).__next__()
        self.assertRaises( ValueError, getattr, pcolumn, "pileups" )

class TestAlignedReadFromBam(unittest.TestCase):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex3.bam"),
                                   "rb" )
        self.reads=list(self.samfile.fetch())

    def testARqname(self):
        self.assertEqual( self.reads[0].qname, "read_28833_29006_6945", "read name mismatch in read 1: %s != %s" % (self.reads[0].qname, "read_28833_29006_6945") )
        self.assertEqual( self.reads[1].qname, "read_28701_28881_323b", "read name mismatch in read 2: %s != %s" % (self.reads[1].qname, "read_28701_28881_323b") )

    def testARflag(self):
        self.assertEqual( self.reads[0].flag, 99, "flag mismatch in read 1: %s != %s" % (self.reads[0].flag, 99) )
        self.assertEqual( self.reads[1].flag, 147, "flag mismatch in read 2: %s != %s" % (self.reads[1].flag, 147) )

    def testARrname(self):
        self.assertEqual( self.reads[0].rname, 0, "chromosome/target id mismatch in read 1: %s != %s" % (self.reads[0].rname, 0) )
        self.assertEqual( self.reads[1].rname, 1, "chromosome/target id mismatch in read 2: %s != %s" % (self.reads[1].rname, 1) )

    def testARpos(self):
        self.assertEqual( self.reads[0].pos, 33-1, "mapping position mismatch in read 1: %s != %s" % (self.reads[0].pos, 33-1) )
        self.assertEqual( self.reads[1].pos, 88-1, "mapping position mismatch in read 2: %s != %s" % (self.reads[1].pos, 88-1) )

    def testARmapq(self):
        self.assertEqual( self.reads[0].mapq, 20, "mapping quality mismatch in read 1: %s != %s" % (self.reads[0].mapq, 20) )
        self.assertEqual( self.reads[1].mapq, 30, "mapping quality mismatch in read 2: %s != %s" % (self.reads[1].mapq, 30) )

    def testARcigar(self):
        self.assertEqual( self.reads[0].cigar, [(0, 10), (2, 1), (0, 25)], "read name length mismatch in read 1: %s != %s" % (self.reads[0].cigar, [(0, 10), (2, 1), (0, 25)]) )
        self.assertEqual( self.reads[1].cigar, [(0, 35)], "read name length mismatch in read 2: %s != %s" % (self.reads[1].cigar, [(0, 35)]) )

    def testARcigarstring(self):
        self.assertEqual( self.reads[0].cigarstring, '10M1D25M' )
        self.assertEqual( self.reads[1].cigarstring, '35M' )

    def testARmrnm(self):
        self.assertEqual( self.reads[0].mrnm, 0, "mate reference sequence name mismatch in read 1: %s != %s" % (self.reads[0].mrnm, 0) )
        self.assertEqual( self.reads[1].mrnm, 1, "mate reference sequence name mismatch in read 2: %s != %s" % (self.reads[1].mrnm, 1) )
        self.assertEqual( self.reads[0].rnext, 0, "mate reference sequence name mismatch in read 1: %s != %s" % (self.reads[0].rnext, 0) )
        self.assertEqual( self.reads[1].rnext, 1, "mate reference sequence name mismatch in read 2: %s != %s" % (self.reads[1].rnext, 1) )

    def testARmpos(self):
        self.assertEqual( self.reads[0].mpos, 200-1, "mate mapping position mismatch in read 1: %s != %s" % (self.reads[0].mpos, 200-1) )
        self.assertEqual( self.reads[1].mpos, 500-1, "mate mapping position mismatch in read 2: %s != %s" % (self.reads[1].mpos, 500-1) )
        self.assertEqual( self.reads[0].pnext, 200-1, "mate mapping position mismatch in read 1: %s != %s" % (self.reads[0].pnext, 200-1) )
        self.assertEqual( self.reads[1].pnext, 500-1, "mate mapping position mismatch in read 2: %s != %s" % (self.reads[1].pnext, 500-1) )

    def testARisize(self):
        self.assertEqual( self.reads[0].isize, 167, "insert size mismatch in read 1: %s != %s" % (self.reads[0].isize, 167) )
        self.assertEqual( self.reads[1].isize, 412, "insert size mismatch in read 2: %s != %s" % (self.reads[1].isize, 412) )
        self.assertEqual( self.reads[0].tlen, 167, "insert size mismatch in read 1: %s != %s" % (self.reads[0].tlen, 167) )
        self.assertEqual( self.reads[1].tlen, 412, "insert size mismatch in read 2: %s != %s" % (self.reads[1].tlen, 412) )

    def testARseq(self):
        self.assertEqual( self.reads[0].seq, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG", "sequence mismatch in read 1: %s != %s" % (self.reads[0].seq, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG") )
        self.assertEqual( self.reads[1].seq, b"ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA", "sequence size mismatch in read 2: %s != %s" % (self.reads[1].seq, b"ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA") )
        self.assertEqual( self.reads[3].seq, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG", "sequence mismatch in read 4: %s != %s" % (self.reads[3].seq, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG") )

    def testARqual(self):
        self.assertEqual( self.reads[0].qual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<", "quality string mismatch in read 1: %s != %s" % (self.reads[0].qual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<") )
        self.assertEqual( self.reads[1].qual, b"<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<", "quality string mismatch in read 2: %s != %s" % (self.reads[1].qual, b"<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<") )
        self.assertEqual( self.reads[3].qual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<", "quality string mismatch in read 3: %s != %s" % (self.reads[3].qual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<") )

    def testARquery(self):
        self.assertEqual( self.reads[0].query, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG", "query mismatch in read 1: %s != %s" % (self.reads[0].query, b"AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG") )
        self.assertEqual( self.reads[1].query, b"ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA", "query size mismatch in read 2: %s != %s" % (self.reads[1].query, b"ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA") )
        self.assertEqual( self.reads[3].query, b"TAGCTAGCTACCTATATCTTGGTCTT", "query mismatch in read 4: %s != %s" % (self.reads[3].query, b"TAGCTAGCTACCTATATCTTGGTCTT") )

    def testARqqual(self):
        self.assertEqual( self.reads[0].qqual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<", "qquality string mismatch in read 1: %s != %s" % (self.reads[0].qqual, b"<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<") )
        self.assertEqual( self.reads[1].qqual, b"<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<", "qquality string mismatch in read 2: %s != %s" % (self.reads[1].qqual, b"<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<") )
        self.assertEqual( self.reads[3].qqual, b"<<<<<<<<<<<<<<<<<:<9/,&,22", "qquality string mismatch in read 3: %s != %s" % (self.reads[3].qqual, b"<<<<<<<<<<<<<<<<<:<9/,&,22") )

    def testPresentOptionalFields(self):
        self.assertEqual( self.reads[0].opt('NM'), 1, "optional field mismatch in read 1, NM: %s != %s" % (self.reads[0].opt('NM'), 1) )
        self.assertEqual( self.reads[0].opt('RG'), 'L1', "optional field mismatch in read 1, RG: %s != %s" % (self.reads[0].opt('RG'), 'L1') )
        self.assertEqual( self.reads[1].opt('RG'), 'L2', "optional field mismatch in read 2, RG: %s != %s" % (self.reads[1].opt('RG'), 'L2') )
        self.assertEqual( self.reads[1].opt('MF'), 18, "optional field mismatch in read 2, MF: %s != %s" % (self.reads[1].opt('MF'), 18) )

    def testPairedBools(self):
        self.assertEqual( self.reads[0].is_paired, True, "is paired mismatch in read 1: %s != %s" % (self.reads[0].is_paired, True) )
        self.assertEqual( self.reads[1].is_paired, True, "is paired mismatch in read 2: %s != %s" % (self.reads[1].is_paired, True) )
        self.assertEqual( self.reads[0].is_proper_pair, True, "is proper pair mismatch in read 1: %s != %s" % (self.reads[0].is_proper_pair, True) )
        self.assertEqual( self.reads[1].is_proper_pair, True, "is proper pair mismatch in read 2: %s != %s" % (self.reads[1].is_proper_pair, True) )

    def testTags( self ):
        self.assertEqual( self.reads[0].tags, 
                          [('NM', 1), ('RG', 'L1'), 
                           ('PG', 'P1'), ('XT', 'U')] )
        self.assertEqual( self.reads[1].tags, 
                          [('MF', 18), ('RG', 'L2'), 
                           ('PG', 'P2'),('XT', 'R') ] )

    def testAddTags( self ):
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([('NM', 1), ('RG', 'L1'), 
                           ('PG', 'P1'), ('XT', 'U')]))
        
        self.reads[0].setTag('X1', 'C')
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([('X1', 'C'), ('NM', 1), ('RG', 'L1'), 
                           ('PG', 'P1'), ('XT', 'U'), ]))
        self.reads[0].setTag('X2', 5)
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X2', 5),('X1', 'C'), 
                                   ('NM', 1), ('RG', 'L1'), 
                                   ('PG', 'P1'), ('XT', 'U'), ]))
        # add with replacement 
        self.reads[0].setTag('X2', 10)
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X2', 10),('X1', 'C'), 
                                   ('NM', 1), ('RG', 'L1'), 
                                   ('PG', 'P1'), ('XT', 'U'), ]))

        # add without replacement 
        self.reads[0].setTag('X2', 5, replace = False)
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X2', 10),('X1', 'C'), 
                                   ('X2', 5),
                                   ('NM', 1), ('RG', 'L1'), 
                                   ('PG', 'P1'), ('XT', 'U'), ]))

    def testAddTagsType( self ):
        self.reads[0].tags = None
        self.reads[0].setTag('X1', 5.0)
        self.reads[0].setTag('X2', "5.0")
        self.reads[0].setTag('X3', 5)
        
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X1', 5.0), 
                                   ('X2', "5.0"),
                                   ('X3', 5) ]))

        # test setting float for int value
        self.reads[0].setTag('X4', 5, value_type = 'd')
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X1', 5.0), 
                                   ('X2', "5.0"),
                                   ('X3', 5),
                                   ('X4', 5.0) ]))

        # test setting int for float value - the
        # value will be rounded.
        self.reads[0].setTag('X5', 5.2, value_type = 'i')
        self.assertEqual( sorted(self.reads[0].tags), 
                          sorted([ ('X1', 5.0), 
                                   ('X2', "5.0"),
                                   ('X3', 5),
                                   ('X4', 5.0),
                                   ('X5', 5)]))

        # test setting invalid type code
        self.assertRaises( ValueError, self.reads[0].setTag, 'X6', 5.2, 'g')

    def testTagsUpdatingFloat( self ):
        self.assertEqual( self.reads[0].tags, 
                          [('NM', 1), ('RG', 'L1'), 
                           ('PG', 'P1'), ('XT', 'U')] )
        self.reads[0].tags += [('XC', 5.0)]
        self.assertEqual( self.reads[0].tags, 
                          [('NM', 1), ('RG', 'L1'), 
                           ('PG', 'P1'), ('XT', 'U'), ('XC', 5.0)] )

    def testOpt( self ):
        self.assertEqual( self.reads[0].opt("XT"), "U" )
        self.assertEqual( self.reads[1].opt("XT"), "R" )

    def testMissingOpt( self ):
        self.assertRaises( KeyError, self.reads[0].opt, "XP" )

    def testEmptyOpt( self ):
        self.assertRaises( KeyError, self.reads[2].opt, "XT" )

    def tearDown(self):
        self.samfile.close()

class TestAlignedReadFromSam(TestAlignedReadFromBam):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex3.sam"),
                                   "r")
        self.reads=list(self.samfile.fetch())

# needs to be implemented 
# class TestAlignedReadFromSamWithoutHeader(TestAlignedReadFromBam):
#
#     def setUp(self):
#         self.samfile=pysam.Samfile( "ex7.sam","r" )
#         self.reads=list(self.samfile.fetch())

class TestHeaderSam(unittest.TestCase):

    header = {'SQ': [{'LN': 1575, 'SN': 'chr1'}, 
                     {'LN': 1584, 'SN': 'chr2'}], 
              'RG': [{'LB': 'SC_1', 'ID': 'L1', 'SM': 'NA12891', 'PU': 'SC_1_10', "CN":"name:with:colon"}, 
                     {'LB': 'SC_2', 'ID': 'L2', 'SM': 'NA12891', 'PU': 'SC_2_12', "CN":"name:with:colon"}],
              'PG': [{'ID': 'P1', 'VN': '1.0'}, {'ID': 'P2', 'VN': '1.1'}], 
              'HD': {'VN': '1.0'},
              'CO' : [ 'this is a comment', 'this is another comment'],
              }

    def compareHeaders( self, a, b ):
        '''compare two headers a and b.'''
        for ak,av in a.items():
            self.assertTrue( ak in b, "key '%s' not in '%s' " % (ak,b) )
            self.assertEqual( av, b[ak] )

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex3.sam"),
                                   "r")

    def testHeaders(self):
        self.compareHeaders( self.header, self.samfile.header )
        self.compareHeaders( self.samfile.header, self.header )

    def testNameMapping( self ):
        for x, y in enumerate( ("chr1", "chr2")):
            tid = self.samfile.gettid( y )
            ref = self.samfile.getrname( x )
            self.assertEqual( tid, x )
            self.assertEqual( ref, y )

        self.assertEqual( self.samfile.gettid("chr?"), -1 )
        self.assertRaises( ValueError, self.samfile.getrname, 2 )

    def tearDown(self):
        self.samfile.close()

class TestHeaderBam(TestHeaderSam):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex3.bam"),
                                   "rb" )

class TestHeaderFromRefs( unittest.TestCase ):
    '''see issue 144

    reference names need to be converted to string for python 3
    '''

    # def testHeader( self ):
    #     refs = ['chr1', 'chr2']
    #     tmpfile = "tmp_%i" % id(self)
    #     s = pysam.Samfile(tmpfile, 'wb', 
    #                       referencenames=refs, 
    #                       referencelengths=[100]*len(refs))
    #     s.close()
        
    #     self.assertTrue( checkBinaryEqual( 'issue144.bam', tmpfile ),
    #                      'bam files differ')
    #     os.unlink( tmpfile )
        
class TestHeader1000Genomes( unittest.TestCase ):
    '''see issue 110'''
    # bamfile = "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/phase2b_alignment/data/NA07048/exome_alignment/NA07048.unmapped.ILLUMINA.bwa.CEU.exome.20120522_p2b.bam"
    bamfile = "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/phase3_EX_or_LC_only_alignment/data/HG00104/alignment/HG00104.chrom11.ILLUMINA.bwa.GBR.low_coverage.20130415.bam"
        
    def testRead( self ):

        f = pysam.Samfile( self.bamfile, "rb" )
        data = f.header.copy()
        self.assertTrue( data )

class TestUnmappedReads(unittest.TestCase):

    def testSAM(self):
        samfile=pysam.Samfile(os.path.join(DATADIR,"ex5.sam"),
                              "r")
        self.assertEqual( len(list(samfile.fetch( until_eof = True))), 2 ) 
        samfile.close()

    def testBAM(self):
        samfile=pysam.Samfile(os.path.join(DATADIR,"ex5.bam"),
                              "rb" )
        self.assertEqual( len(list(samfile.fetch( until_eof = True))), 2 ) 
        samfile.close()

class TestPileupObjects(unittest.TestCase):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                   "rb")

    def testPileupColumn(self):
        for pcolumn1 in self.samfile.pileup( region="chr1:105" ):
            if pcolumn1.pos == 104:
                self.assertEqual( pcolumn1.tid, 0, "chromosome/target id mismatch in position 1: %s != %s" % (pcolumn1.tid, 0) )
                self.assertEqual( pcolumn1.pos, 105-1, "position mismatch in position 1: %s != %s" % (pcolumn1.pos, 105-1) )
                self.assertEqual( pcolumn1.n, 2, "# reads mismatch in position 1: %s != %s" % (pcolumn1.n, 2) )
        for pcolumn2 in self.samfile.pileup( region="chr2:1480" ):
            if pcolumn2.pos == 1479:
                self.assertEqual( pcolumn2.tid, 1, "chromosome/target id mismatch in position 1: %s != %s" % (pcolumn2.tid, 1) )
                self.assertEqual( pcolumn2.pos, 1480-1, "position mismatch in position 1: %s != %s" % (pcolumn2.pos, 1480-1) )
                self.assertEqual( pcolumn2.n, 12, "# reads mismatch in position 1: %s != %s" % (pcolumn2.n, 12) )

    def testPileupRead(self):
        for pcolumn1 in self.samfile.pileup( region="chr1:105" ):
            if pcolumn1.pos == 104:
                self.assertEqual( len(pcolumn1.pileups), 2, "# reads aligned to column mismatch in position 1: %s != %s" % (len(pcolumn1.pileups), 2) )
#                self.assertEqual( pcolumn1.pileups[0]  # need to test additional properties here

    def tearDown(self):
        self.samfile.close()

    def testIteratorOutOfScope( self ):
        '''test if exception is raised if pileup col is accessed after iterator is exhausted.'''

        for pileupcol in self.samfile.pileup():
            pass
        
        self.assertRaises( ValueError, getattr, pileupcol, "pileups" )

class TestContextManager(unittest.TestCase):

    def testManager( self ):
        with pysam.Samfile(os.path.join(DATADIR,'ex1.bam'),
                           'rb') as samfile:
            samfile.fetch()
        self.assertEqual( samfile._isOpen(), False )

class TestExceptions(unittest.TestCase):

    def setUp(self):
        self.samfile=pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                   "rb")

    def testMissingFile(self):

        self.assertRaises( IOError, pysam.Samfile, "exdoesntexist.bam", "rb" )
        self.assertRaises( IOError, pysam.Samfile, "exdoesntexist.sam", "r" )
        self.assertRaises( IOError, pysam.Samfile, "exdoesntexist.bam", "r" )
        self.assertRaises( IOError, pysam.Samfile, "exdoesntexist.sam", "rb" )

    def testBadContig(self):
        self.assertRaises( ValueError, self.samfile.fetch, "chr88" )

    def testMeaninglessCrap(self):
        self.assertRaises( ValueError, self.samfile.fetch, "skljf" )

    def testBackwardsOrderNewFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, 'chr1', 100, 10 )

    def testBackwardsOrderOldFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, region="chr1:100-10")
        
    def testOutOfRangeNegativeNewFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, "chr1", 5, -10 )
        self.assertRaises( ValueError, self.samfile.fetch, "chr1", 5, 0 )
        self.assertRaises( ValueError, self.samfile.fetch, "chr1", -5, -10 )

        self.assertRaises( ValueError, self.samfile.count, "chr1", 5, -10 )
        self.assertRaises( ValueError, self.samfile.count, "chr1", 5, 0 )        
        self.assertRaises( ValueError, self.samfile.count, "chr1", -5, -10 )

    def testOutOfRangeNegativeOldFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, region="chr1:-5-10" )
        self.assertRaises( ValueError, self.samfile.fetch, region="chr1:-5-0" )
        self.assertRaises( ValueError, self.samfile.fetch, region="chr1:-5--10" )

        self.assertRaises( ValueError, self.samfile.count, region="chr1:-5-10" )
        self.assertRaises( ValueError, self.samfile.count, region="chr1:-5-0" )
        self.assertRaises( ValueError, self.samfile.count, region="chr1:-5--10" )

    def testOutOfRangNewFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, "chr1", 9999999999, 99999999999 )
        self.assertRaises( ValueError, self.samfile.count, "chr1", 9999999999, 99999999999 )

    def testOutOfRangeLargeNewFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, "chr1", 9999999999999999999999999999999, 9999999999999999999999999999999999999999 )
        self.assertRaises( ValueError, self.samfile.count, "chr1", 9999999999999999999999999999999, 9999999999999999999999999999999999999999 )

    def testOutOfRangeLargeOldFormat(self):
        self.assertRaises( ValueError, self.samfile.fetch, "chr1:99999999999999999-999999999999999999" )
        self.assertRaises( ValueError, self.samfile.count, "chr1:99999999999999999-999999999999999999" )

    def testZeroToZero(self):        
        '''see issue 44'''
        self.assertEqual( len(list(self.samfile.fetch('chr1', 0, 0))), 0)

    def tearDown(self):
        self.samfile.close()

class TestWrongFormat(unittest.TestCase):
    '''test cases for opening files not in bam/sam format.'''

    def testOpenSamAsBam( self ):
        self.assertRaises( ValueError,
                           pysam.Samfile,
                           os.path.join(DATADIR,'ex1.sam'),
                           'rb' )

    def testOpenBamAsSam( self ):
        # test fails, needs to be implemented.
        # sam.fetch() fails on reading, not on opening
        # self.assertRaises( ValueError, pysam.Samfile, 'ex1.bam', 'r' )
        pass

    def testOpenFastaAsSam( self ):
        # test fails, needs to be implemented.
        # sam.fetch() fails on reading, not on opening
        # self.assertRaises( ValueError, pysam.Samfile, 'ex1.fa', 'r' )
        pass

    def testOpenFastaAsBam( self ):
        self.assertRaises( ValueError, 
                           pysam.Samfile,
                           os.path.join(DATADIR,'ex1.fa'),
                           'rb' )

class TestFastaFile(unittest.TestCase):

    mSequences = { 'chr1' :
                       b"CACTAGTGGCTCATTGTAAATGTGTGGTTTAACTCGTCCATGGCCCAGCATTAGGGAGCTGTGGACCCTGCAGCCTGGCTGTGGGGGCCGCAGTGGCTGAGGGGTGCAGAGCCGAGTCACGGGGTTGCCAGCACAGGGGCTTAACCTCTGGTGACTGCCAGAGCTGCTGGCAAGCTAGAGTCCCATTTGGAGCCCCTCTAAGCCGTTCTATTTGTAATGAAAACTATATTTATGCTATTCAGTTCTAAATATAGAAATTGAAACAGCTGTGTTTAGTGCCTTTGTTCAACCCCCTTGCAACAACCTTGAGAACCCCAGGGAATTTGTCAATGTCAGGGAAGGAGCATTTTGTCAGTTACCAAATGTGTTTATTACCAGAGGGATGGAGGGAAGAGGGACGCTGAAGAACTTTGATGCCCTCTTCTTCCAAAGATGAAACGCGTAACTGCGCTCTCATTCACTCCAGCTCCCTGTCACCCAATGGACCTGTGATATCTGGATTCTGGGAAATTCTTCATCCTGGACCCTGAGAGATTCTGCAGCCCAGCTCCAGATTGCTTGTGGTCTGACAGGCTGCAACTGTGAGCCATCACAATGAACAACAGGAAGAAAAGGTCTTTCAAAAGGTGATGTGTGTTCTCATCAACCTCATACACACACATGGTTTAGGGGTATAATACCTCTACATGGCTGATTATGAAAACAATGTTCCCCAGATACCATCCCTGTCTTACTTCCAGCTCCCCAGAGGGAAAGCTTTCAACGCTTCTAGCCATTTCTTTTGGCATTTGCCTTCAGACCCTACACGAATGCGTCTCTACCACAGGGGGCTGCGCGGTTTCCCATCATGAAGCACTGAACTTCCACGTCTCATCTAGGGGAACAGGGAGGTGCACTAATGCGCTCCACGCCCAAGCCCTTCTCACAGTTTCTGCCCCCAGCATGGTTGTACTGGGCAATACATGAGATTATTAGGAAATGCTTTACTGTCATAACTATGAAGAGACTATTGCCAGATGAACCACACATTAATACTATGTTTCTTATCTGCACATTACTACCCTGCAATTAATATAATTGTGTCCATGTACACACGCTGTCCTATGTACTTATCATGACTCTATCCCAAATTCCCAATTACGTCCTATCTTCTTCTTAGGGAAGAACAGCTTAGGTATCAATTTGGTGTTCTGTGTAAAGTCTCAGGGAGCCGTCCGTGTCCTCCCATCTGGCCTCGTCCACACTGGTTCTCTTGAAAGCTTGGGCTGTAATGATGCCCCTTGGCCATCACCCAGTCCCTGCCCCATCTCTTGTAATCTCTCTCCTTTTTGCTGCATCCCTGTCTTCCTCTGTCTTGATTTACTTGTTGTTGGTTTTCTGTTTCTTTGTTTGATTTGGTGGAAGACATAATCCCACGCTTCCTATGGAAAGGTTGTTGGGAGATTTTTAATGATTCCTCAATGTTAAAATGTCTATTTTTGTCTTGACACCCAACTAATATTTGTCTGAGCAAAACAGTCTAGATGAGAGAGAACTTCCCTGGAGGTCTGATGGCGTTTCTCCCTCGTCTTCTTA",
                   'chr2' :
                       b"TTCAAATGAACTTCTGTAATTGAAAAATTCATTTAAGAAATTACAAAATATAGTTGAAAGCTCTAACAATAGACTAAACCAAGCAGAAGAAAGAGGTTCAGAACTTGAAGACAAGTCTCTTATGAATTAACCCAGTCAGACAAAAATAAAGAAAAAAATTTTAAAAATGAACAGAGCTTTCAAGAAGTATGAGATTATGTAAAGTAACTGAACCTATGAGTCACAGGTATTCCTGAGGAAAAAGAAAAAGTGAGAAGTTTGGAAAAACTATTTGAGGAAGTAATTGGGGAAAACCTCTTTAGTCTTGCTAGAGATTTAGACATCTAAATGAAAGAGGCTCAAAGAATGCCAGGAAGATACATTGCAAGACAGACTTCATCAAGATATGTAGTCATCAGACTATCTAAAGTCAACATGAAGGAAAAAAATTCTAAAATCAGCAAGAGAAAAGCATACAGTCATCTATAAAGGAAATCCCATCAGAATAACAATGGGCTTCTCAGCAGAAACCTTACAAGCCAGAAGAGATTGGATCTAATTTTTGGACTTCTTAAAGAAAAAAAAACCTGTCAAACACGAATGTTATGCCCTGCTAAACTAAGCATCATAAATGAAGGGGAAATAAAGTCAAGTCTTTCCTGACAAGCAAATGCTAAGATAATTCATCATCACTAAACCAGTCCTATAAGAAATGCTCAAAAGAATTGTAAAAGTCAAAATTAAAGTTCAATACTCACCATCATAAATACACACAAAAGTACAAAACTCACAGGTTTTATAAAACAATTGAGACTACAGAGCAACTAGGTAAAAAATTAACATTACAACAGGAACAAAACCTCATATATCAATATTAACTTTGAATAAAAAGGGATTAAATTCCCCCACTTAAGAGATATAGATTGGCAGAACAGATTTAAAAACATGAACTAACTATATGCTGTTTACAAGAAACTCATTAATAAAGACATGAGTTCAGGTAAAGGGGTGGAAAAAGATGTTCTACGCAAACAGAAACCAAATGAGAGAAGGAGTAGCTATACTTATATCAGATAAAGCACACTTTAAATCAACAACAGTAAAATAAAACAAAGGAGGTCATCATACAATGATAAAAAGATCAATTCAGCAAGAAGATATAACCATCCTACTAAATACATATGCACCTAACACAAGACTACCCAGATTCATAAAACAAATACTACTAGACCTAAGAGGGATGAGAAATTACCTAATTGGTACAATGTACAATATTCTGATGATGGTTACACTAAAAGCCCATACTTTACTGCTACTCAATATATCCATGTAACAAATCTGCGCTTGTACTTCTAAATCTATAAAAAAATTAAAATTTAACAAAAGTAAATAAAACACATAGCTAAAACTAAAAAAGCAAAAACAAAAACTATGCTAAGTATTGGTAAAGATGTGGGGAAAAAAGTAAACTCTCAAATATTGCTAGTGGGAGTATAAATTGTTTTCCACTTTGGAAAACAATTTGGTAATTTCGTTTTTTTTTTTTTCTTTTCTCTTTTTTTTTTTTTTTTTTTTGCATGCCAGAAAAAAATATTTACAGTAACT",
                   }

    def setUp(self):
        self.file=pysam.Fastafile(os.path.join(DATADIR,"ex1.fa"))

    def testFetch(self):
        for id, seq in list(self.mSequences.items()):
            self.assertEqual( seq, self.file.fetch( id ) )
            for x in range( 0, len(seq), 10):
                self.assertEqual( seq[x:x+10], self.file.fetch( id, x, x+10) )
                # test x:end
                self.assertEqual( seq[x:], self.file.fetch( id, x) )
                # test 0:x
                self.assertEqual( seq[:x], self.file.fetch( id, None, x) )

        
        # unknown sequence returns ""
        # change: should be an IndexError
        self.assertEqual( b"", self.file.fetch("chr12") )

    def testOutOfRangeAccess( self ):
        '''test out of range access.'''
        # out of range access returns an empty string
        for contig, s in self.mSequences.items():
            self.assertEqual( self.file.fetch( contig, len(s), len(s)+1), b"" )

        self.assertEqual( self.file.fetch( "chr3", 0 , 100), b"" ) 

    def testFetchErrors( self ):
        self.assertRaises( ValueError, self.file.fetch )
        self.assertRaises( IndexError, self.file.fetch, "chr1", -1, 10 )
        self.assertRaises( ValueError, self.file.fetch, "chr1", 20, 10 )
        
        # does not work yet
        # self.assertRaises( KeyError, self.file.fetch, "chrX" )

    def testLength( self ):
        self.assertEqual( len(self.file), 2 )
        
    def testSequenceLengths( self ):
        self.assertEqual( 1575, self.file.getReferenceLength( "chr1" ) )
        self.assertEqual( 1584, self.file.getReferenceLength( "chr2" ) )

    def tearDown(self):
        self.file.close()

class TestFastqFile(unittest.TestCase):

    def setUp(self):
        self.file=pysam.Fastqfile(os.path.join(DATADIR,"ex1.fq"))

    def testCounts( self ):
        self.assertEqual( len( [ x for x in self.file ] ), 3270 )

    def testMissingFile( self ):
        self.assertRaises( IOError, pysam.Fastqfile, "nothere.fq" )

    def testSequence( self ):
        s = self.file.__next__()
        # test first entry
        self.assertEqual( s.sequence, b"GGGAACAGGGGGGTGCACTAATGCGCTCCACGCCC")
        self.assertEqual( s.quality, b"<<86<<;<78<<<)<;4<67<;<;<74-7;,;8,;")
        self.assertEqual( s.name, b"B7_589:1:101:825:28" )

        for s in self.file: pass
        # test last entry
        self.assertEqual( s.sequence, b"TAATTGAAAAATTCATTTAAGAAATTACAAAATAT")
        self.assertEqual( s.quality, b"<<<<<;<<<<<<<<<<<<<<<;;;<<<;<<8;<;<")
        self.assertEqual( s.name, b"EAS56_65:8:64:507:478" )

class TestAlignedRead(unittest.TestCase):
    '''tests to check if aligned read can be constructed
    and manipulated.
    '''

    def checkFieldEqual( self, read1, read2, exclude = []):
        '''check if two reads are equal by comparing each field.'''

        for x in ("qname", "seq", "flag",
                  "rname", "pos", "mapq", "cigar",
                  "mrnm", "mpos", "isize", "qual",
                  "is_paired", "is_proper_pair",
                  "is_unmapped", "mate_is_unmapped",
                  "is_reverse", "mate_is_reverse",
                  "is_read1", "is_read2",
                  "is_secondary", "is_qcfail",
                  "is_duplicate", "bin"):
            if x in exclude: continue
            self.assertEqual( getattr(read1, x), getattr(read2,x), "attribute mismatch for %s: %s != %s" % 
                              (x, getattr(read1, x), getattr(read2,x)))
    
    def testEmpty( self ):
        a = pysam.AlignedRead()
        self.assertEqual( a.qname, None )
        self.assertEqual( a.seq, None )
        self.assertEqual( a.qual, None )
        self.assertEqual( a.flag, 0 )
        self.assertEqual( a.rname, 0 )
        self.assertEqual( a.mapq, 0 )
        self.assertEqual( a.cigar, None )
        self.assertEqual( a.tags, [] )
        self.assertEqual( a.mrnm, 0 )
        self.assertEqual( a.mpos, 0 )
        self.assertEqual( a.isize, 0 )

    def buildRead( self ):
        '''build an example read.'''
        
        a = pysam.AlignedRead()
        a.qname = "read_12345"
        a.seq="ACGT" * 10
        a.flag = 0
        a.rname = 0
        a.pos = 20
        a.mapq = 20
        a.cigar = ( (0,10), (2,1), (0,9), (1,1), (0,20) )
        a.mrnm = 0
        a.mpos=200
        a.isize=167
        a.qual="1234" * 10
        # todo: create tags
        return a

    def testUpdate( self ):
        '''check if updating fields affects other variable length data
        '''
        a = self.buildRead()
        b = self.buildRead()

        # check qname
        b.qname = "read_123"
        self.checkFieldEqual( a, b, "qname" )
        b.qname = "read_12345678"
        self.checkFieldEqual( a, b, "qname" )
        b.qname = "read_12345"
        self.checkFieldEqual( a, b)

        # check cigar
        b.cigar = ( (0,10), )
        self.checkFieldEqual( a, b, "cigar" )
        b.cigar = ( (0,10), (2,1), (0,10) )
        self.checkFieldEqual( a, b, "cigar" )
        b.cigar = ( (0,10), (2,1), (0,9), (1,1), (0,20) )
        self.checkFieldEqual( a, b)

        # check seq 
        b.seq = "ACGT"
        self.checkFieldEqual( a, b, ("seq", "qual") )
        b.seq = "ACGT" * 3
        self.checkFieldEqual( a, b, ("seq", "qual") )
        b.seq = "ACGT" * 10
        self.checkFieldEqual( a, b, ("qual",))

        # reset qual
        b = self.buildRead()

        # check flags:
        for x in (
            "is_paired", "is_proper_pair",
            "is_unmapped", "mate_is_unmapped",
            "is_reverse", "mate_is_reverse",
            "is_read1", "is_read2",
            "is_secondary", "is_qcfail",
            "is_duplicate"):
            setattr( b, x, True )
            self.assertEqual( getattr(b, x), True )
            self.checkFieldEqual( a, b, ("flag", x,) )
            setattr( b, x, False )
            self.assertEqual( getattr(b, x), False )
            self.checkFieldEqual( a, b )

    def testUpdate( self ):
        '''issue 135: inplace update of sequence and quality score.
        
        This does not work as setting the sequence will erase
        the quality scores.
        '''
        a = self.buildRead()
        a.seq = a.seq[5:10]
        self.assertEqual( a.qual, None )
        
        a = self.buildRead()
        s = a.qual
        a.seq = a.seq[5:10]
        a.qual = s[5:10]
        
        self.assertEqual( a.qual, s[5:10])

    def testLargeRead( self ):
        '''build an example read.'''
        
        a = pysam.AlignedRead()
        a.qname = "read_12345"
        a.seq="ACGT" * 200
        a.flag = 0
        a.rname = 0
        a.pos = 20
        a.mapq = 20
        a.cigar = ( (0, 4 * 200), )
        a.mrnm = 0
        a.mpos=200
        a.isize=167
        a.qual="1234" * 200

        return a

    def testTagParsing( self ):
        '''test for tag parsing

        see http://groups.google.com/group/pysam-user-group/browse_thread/thread/67ca204059ea465a
        '''
        samfile=pysam.Samfile(os.path.join(DATADIR,"ex8.bam"),
                              "rb")

        for entry in samfile:
            before = entry.tags
            entry.tags = entry.tags
            after = entry.tags
            self.assertEqual( after, before )

    def testUpdateTlen( self ):
        '''check if updating tlen works'''
        a = self.buildRead()
        oldlen = a.tlen
        oldlen *= 2
        a.tlen = oldlen
        self.assertEqual( a.tlen, oldlen )

    def testPositions( self ):
        a = self.buildRead()
        self.assertEqual( a.positions,
                          [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 
                                31, 32, 33, 34, 35, 36, 37, 38, 39, 
                           40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 
                           50, 51, 52, 53, 54, 55, 56, 57, 58, 59] )

        self.assertEqual( a.aligned_pairs,
                          [(0, 20), (1, 21), (2, 22), (3, 23), (4, 24), 
                           (5, 25), (6, 26), (7, 27), (8, 28), (9, 29), 
                           (None, 30), 
                           (10, 31), (11, 32), (12, 33), (13, 34), (14, 35), 
                           (15, 36), (16, 37), (17, 38), (18, 39), (19, None), 
                           (20, 40), (21, 41), (22, 42), (23, 43), (24, 44), 
                           (25, 45), (26, 46), (27, 47), (28, 48), (29, 49), 
                           (30, 50), (31, 51), (32, 52), (33, 53), (34, 54), 
                           (35, 55), (36, 56), (37, 57), (38, 58), (39, 59)] )

        self.assertEqual( a.positions, [x[1] for x in a.aligned_pairs if x[0] != None and x[1] != None] )
        # alen is the length of the aligned read in genome
        self.assertEqual( a.alen, a.aligned_pairs[-1][0] + 1 )
        # aend points to one beyond last aligned base in ref
        self.assertEqual( a.positions[-1], a.aend - 1 )

class TestDeNovoConstruction(unittest.TestCase):
    '''check BAM/SAM file construction using ex6.sam
    
    (note these are +1 coordinates):
    
    read_28833_29006_6945	99	chr1	33	20	10M1D25M	=	200	167	AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG	<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<	NM:i:1	RG:Z:L1
    read_28701_28881_323b	147	chr2	88	30	35M	=	500	412	ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA	<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<	MF:i:18	RG:Z:L2
    '''

    header = { 'HD': {'VN': '1.0'},
               'SQ': [{'LN': 1575, 'SN': 'chr1'}, 
                      {'LN': 1584, 'SN': 'chr2'}], }

    bamfile = os.path.join(DATADIR, "ex6.bam")
    samfile = os.path.join(DATADIR, "ex6.sam")

    def checkFieldEqual( self, read1, read2, exclude = []):
        '''check if two reads are equal by comparing each field.'''

        for x in ("qname", "seq", "flag",
                  "rname", "pos", "mapq", "cigar",
                  "mrnm", "mpos", "isize", "qual",
                  "bin",
                  "is_paired", "is_proper_pair",
                  "is_unmapped", "mate_is_unmapped",
                  "is_reverse", "mate_is_reverse",
                  "is_read1", "is_read2",
                  "is_secondary", "is_qcfail",
                  "is_duplicate"):
            if x in exclude: continue
            self.assertEqual( getattr(read1, x), getattr(read2,x), "attribute mismatch for %s: %s != %s" % 
                              (x, getattr(read1, x), getattr(read2,x)))

    def setUp( self ):

        a = pysam.AlignedRead()
        a.qname = "read_28833_29006_6945"
        a.seq="AGCTTAGCTAGCTACCTATATCTTGGTCTTGGCCG"
        a.flag = 99
        a.rname = 0
        a.pos = 32
        a.mapq = 20
        a.cigar = ( (0,10), (2,1), (0,25) )
        a.mrnm = 0
        a.mpos=199
        a.isize=167
        a.qual="<<<<<<<<<<<<<<<<<<<<<:<9/,&,22;;<<<"
        a.tags = ( ("NM", 1),
                   ("RG", "L1") )

        b = pysam.AlignedRead()
        b.qname = "read_28701_28881_323b"
        b.seq="ACCTATATCTTGGCCTTGGCCGATGCGGCCTTGCA"
        b.flag = 147
        b.rname = 1
        b.pos = 87
        b.mapq = 30
        b.cigar = ( (0,35), )
        b.mrnm = 1
        b.mpos=499
        b.isize=412
        b.qual="<<<<<;<<<<7;:<<<6;<<<<<<<<<<<<7<<<<"
        b.tags = ( ("MF", 18),
                   ("RG", "L2") )

        self.reads = (a,b)

    def testSAMWholeFile( self ):
        
        tmpfilename = "tmp_%i.sam" % id(self)

        outfile = pysam.Samfile(tmpfilename, 
                                "wh", 
                                header = self.header )

        for x in self.reads: outfile.write( x )
        outfile.close()
        self.assertTrue( checkBinaryEqual( tmpfilename, self.samfile ),
                         "mismatch when construction SAM file, see %s %s" % (tmpfilename, self.samfile))
        
        os.unlink( tmpfilename )

    def testBAMPerRead( self ):
        '''check if individual reads are binary equal.'''
        infile = pysam.Samfile(self.bamfile, "rb")

        others = list(infile)
        for denovo, other in zip( others, self.reads):
            self.checkFieldEqual( other, denovo )
            self.assertEqual(other.compare( denovo ), 0 )

    def testSAMPerRead( self ):
        '''check if individual reads are binary equal.'''
        infile = pysam.Samfile(self.samfile, "r")

        others = list(infile)
        for denovo, other in zip( others, self.reads):
            self.checkFieldEqual(other, denovo )
            self.assertEqual(other.compare( denovo), 0 )
            
    def testBAMWholeFile( self ):
        
        tmpfilename = "tmp_%i.bam" % id(self)

        outfile = pysam.Samfile( tmpfilename, "wb", header = self.header )

        for x in self.reads: outfile.write( x )
        outfile.close()
        
        self.assertTrue( checkBinaryEqual( tmpfilename, self.bamfile ),
                         "mismatch when construction BAM file, see %s %s" % (tmpfilename, self.bamfile))
        
        os.unlink( tmpfilename )

class TestDeNovoConstructionUserTags(TestDeNovoConstruction):
    '''test de novo construction with a header that contains lower-case tags.'''

    header = { 'HD': {'VN': '1.0'},
               'SQ': [{'LN': 1575, 'SN': 'chr1'}, 
                      {'LN': 1584, 'SN': 'chr2'}],
               'x1': {'A': 2, 'B': 5 },
               'x3': {'A': 6, 'B': 5 },
               'x2': {'A': 4, 'B': 5 } }

    bamfile = os.path.join(DATADIR,"example_user_header.bam")
    samfile = os.path.join(DATADIR,"example_user_header.sam")

class TestEmptyHeader( unittest.TestCase ):
    '''see issue 84.'''
    
    def testEmptyHeader( self ):

        s = pysam.Samfile(os.path.join(DATADIR,'example_empty_header.bam'))
        self.assertEqual( s.header, {'SQ': [{'LN': 1000, 'SN': 'chr1'}]} )

class TestBTagSam( unittest.TestCase ):
    '''see issue 81.'''
    
    compare = [ [100, 1, 91, 0, 7, 101, 0, 201, 96, 204, 0, 0, 87, 109, 0, 7, 97, 112, 1, 12, 78, 197, 0, 7, 100, 95, 101, 202, 0, 6, 0, 1, 186, 0, 84, 0, 244, 0, 0, 324, 0, 107, 195, 101, 113, 0, 102, 0, 104, 3, 0, 101, 1, 0, 212, 6, 0, 0, 1, 0, 74, 1, 11, 0, 196, 2, 197, 103, 0, 108, 98, 2, 7, 0, 1, 2, 194, 0, 180, 0, 108, 0, 203, 104, 16, 5, 205, 0, 0, 0, 1, 1, 100, 98, 0, 0, 204, 6, 0, 79, 0, 0, 101, 7, 109, 90, 265, 1, 27, 10, 109, 102, 9, 0, 292, 0, 110, 0, 0, 102, 112, 0, 0, 84, 100, 103, 2, 81, 126, 0, 2, 90, 0, 15, 96, 15, 1, 0, 2, 0, 107, 92, 0, 0, 101, 3, 98, 15, 102, 13, 116, 116, 90, 93, 198, 0, 0, 0, 199, 92, 26, 495, 100, 5, 0, 100, 5, 209, 0, 92, 107, 90, 0, 0, 0, 0, 109, 194, 7, 94, 200, 0, 40, 197, 0, 11, 0, 0, 112, 110, 6, 4, 200, 28, 0, 196, 0, 203, 1, 129, 0, 0, 1, 0, 94, 0, 1, 0, 107, 5, 201, 3, 3, 100, 0, 121, 0, 7, 0, 1, 105, 306, 3, 86, 8, 183, 0, 12, 163, 17, 83, 22, 0, 0, 1, 8, 109, 103, 0, 0, 295, 0, 200, 16, 172, 3, 16, 182, 3, 11, 0, 0, 223, 111, 103, 0, 5, 225, 0, 95],
                [-100,200,-300,-400],
                [-100,12],
                [12,15],
                [-1.0,5.0,2.5] ]
            
    filename = os.path.join(DATADIR,'example_btag.sam')

    def testRead( self ):

        s = pysam.Samfile(self.filename)
        for x, read in enumerate(s):
            if x == 0:
                self.assertEqual( read.tags, [('RG', 'QW85I'), ('PG', 'tmap'), ('MD', '140'), ('NM', 0), ('AS', 140), ('FZ', [100, 1, 91, 0, 7, 101, 0, 201, 96, 204, 0, 0, 87, 109, 0, 7, 97, 112, 1, 12, 78, 197, 0, 7, 100, 95, 101, 202, 0, 6, 0, 1, 186, 0, 84, 0, 244, 0, 0, 324, 0, 107, 195, 101, 113, 0, 102, 0, 104, 3, 0, 101, 1, 0, 212, 6, 0, 0, 1, 0, 74, 1, 11, 0, 196, 2, 197, 103, 0, 108, 98, 2, 7, 0, 1, 2, 194, 0, 180, 0, 108, 0, 203, 104, 16, 5, 205, 0, 0, 0, 1, 1, 100, 98, 0, 0, 204, 6, 0, 79, 0, 0, 101, 7, 109, 90, 265, 1, 27, 10, 109, 102, 9, 0, 292, 0, 110, 0, 0, 102, 112, 0, 0, 84, 100, 103, 2, 81, 126, 0, 2, 90, 0, 15, 96, 15, 1, 0, 2, 0, 107, 92, 0, 0, 101, 3, 98, 15, 102, 13, 116, 116, 90, 93, 198, 0, 0, 0, 199, 92, 26, 495, 100, 5, 0, 100, 5, 209, 0, 92, 107, 90, 0, 0, 0, 0, 109, 194, 7, 94, 200, 0, 40, 197, 0, 11, 0, 0, 112, 110, 6, 4, 200, 28, 0, 196, 0, 203, 1, 129, 0, 0, 1, 0, 94, 0, 1, 0, 107, 5, 201, 3, 3, 100, 0, 121, 0, 7, 0, 1, 105, 306, 3, 86, 8, 183, 0, 12, 163, 17, 83, 22, 0, 0, 1, 8, 109, 103, 0, 0, 295, 0, 200, 16, 172, 3, 16, 182, 3, 11, 0, 0, 223, 111, 103, 0, 5, 225, 0, 95]), ('XA', 'map2-1'), ('XS', 53), ('XT', 38), ('XF', 1), ('XE', 0)] 
                                  )
                         
            fz = dict(read.tags)["FZ"]
            self.assertEqual( fz, self.compare[x] )
            self.assertEqual( read.opt("FZ"), self.compare[x])

    def testWrite( self ):
        
        s = pysam.Samfile(self.filename)
        for read in s:
            before = read.tags
            read.tags = read.tags
            after = read.tags
            self.assertEqual( after, before )

class TestBTagBam( TestBTagSam ):
    filename = os.path.join(DATADIR,'example_btag.bam')

class TestDoubleFetch(unittest.TestCase):
    '''check if two iterators on the same bamfile are independent.'''
    
    filename = os.path.join(DATADIR, 'ex1.bam')

    def testDoubleFetch( self ):

        samfile1 = pysam.Samfile(self.filename, 'rb')

        for a,b in zip(samfile1.fetch(), samfile1.fetch()):
            self.assertEqual( a.compare( b ), 0 )

    def testDoubleFetchWithRegion( self ):

        samfile1 = pysam.Samfile(self.filename, 'rb')
        chr, start, stop = 'chr1', 200, 3000000
        self.assertTrue(len(list(samfile1.fetch ( chr, start, stop))) > 0) #just making sure the test has something to catch

        for a,b in zip(samfile1.fetch( chr, start, stop), samfile1.fetch( chr, start, stop)):
            self.assertEqual( a.compare( b ), 0 ) 

    def testDoubleFetchUntilEOF( self ):

        samfile1 = pysam.Samfile(self.filename, 'rb')

        for a,b in zip(samfile1.fetch( until_eof = True), 
                       samfile1.fetch( until_eof = True )):
            self.assertEqual( a.compare( b), 0 )

class TestRemoteFileFTP(unittest.TestCase):
    '''test remote access.

    '''

    # Need to find an ftp server without password on standard
    # port.

    url = "ftp://ftp.sanger.ac.uk/pub/rd/humanSequences/CV.bam"
    region = "1:1-1000"

    def testFTPView( self ):
        return
        result = pysam.view( self.url, self.region )
        self.assertEqual( len(result), 36 )
        
    def testFTPFetch( self ):
        return
        samfile = pysam.Samfile(self.url, "rb")  
        result = list(samfile.fetch( region = self.region ))
        self.assertEqual( len(result), 36 )

class TestRemoteFileHTTP( unittest.TestCase):

    url = "http://genserv.anat.ox.ac.uk/downloads/pysam/test/ex1.bam"
    region = "chr1:1-1000"
    local = os.path.join(DATADIR,"ex1.bam")

    def testView( self ):
        samfile_local = pysam.Samfile(self.local, "rb")  
        ref = list(samfile_local.fetch( region = self.region ))
        
        result = pysam.view( self.url, self.region )
        self.assertEqual( len(result), len(ref) )
        
    def testFetch( self ):
        samfile = pysam.Samfile(self.url, "rb")  
        result = list(samfile.fetch( region = self.region ))
        samfile_local = pysam.Samfile(self.local, "rb")  
        ref = list(samfile_local.fetch( region = self.region ))

        self.assertEqual( len(ref), len(result) )
        for x, y in zip(result, ref):
            self.assertEqual( x.compare( y ), 0 )

    def testFetchAll( self ):
        samfile = pysam.Samfile(self.url, "rb")  
        result = list(samfile.fetch())
        samfile_local = pysam.Samfile(self.local, "rb")  
        ref = list(samfile_local.fetch() )

        self.assertEqual( len(ref), len(result) )
        for x, y in zip(result, ref):
            self.assertEqual( x.compare( y ), 0 )

class TestLargeOptValues( unittest.TestCase ):

    ints = ( 65536, 214748, 2147484, 2147483647 )
    floats = ( 65536.0, 214748.0, 2147484.0 )

    def check( self, samfile ):
        
        i = samfile.fetch()
        for exp in self.ints:
            rr = next(i)
            obs = rr.opt("ZP")
            self.assertEqual( exp, obs, "expected %s, got %s\n%s" % (str(exp), str(obs), str(rr)))

        for exp in [ -x for x in self.ints ]:
            rr = next(i)
            obs = rr.opt("ZP")
            self.assertEqual( exp, obs, "expected %s, got %s\n%s" % (str(exp), str(obs), str(rr)))

        for exp in self.floats:
            rr = next(i)
            obs = rr.opt("ZP")
            self.assertEqual( exp, obs, "expected %s, got %s\n%s" % (str(exp), str(obs), str(rr)))

        for exp in [ -x for x in self.floats ]:
            rr = next(i)
            obs = rr.opt("ZP")
            self.assertEqual( exp, obs, "expected %s, got %s\n%s" % (str(exp), str(obs), str(rr)))

    def testSAM( self ):
        samfile = pysam.Samfile(os.path.join(DATADIR,"ex10.sam"),
                                "r")
        self.check( samfile )

    def testBAM( self ):
        samfile = pysam.Samfile(os.path.join(DATADIR,"ex10.bam"),
                                "rb")
        self.check( samfile )

# class TestSNPCalls( unittest.TestCase ):
#     '''test pysam SNP calling ability.'''

#     def checkEqual( self, a, b ):
#         for x in ("reference_base", 
#                   "pos",
#                   "genotype",
#                   "consensus_quality",
#                   "snp_quality",
#                   "mapping_quality",
#                   "coverage" ):
#             self.assertEqual( getattr(a, x), getattr(b,x), "%s mismatch: %s != %s\n%s\n%s" % 
#                               (x, getattr(a, x), getattr(b,x), str(a), str(b)))

#     def testAllPositionsViaIterator( self ):
#         samfile = pysam.Samfile( "ex1.bam", "rb")  
#         fastafile = pysam.Fastafile( "ex1.fa" )
#         try: 
#             refs = [ x for x in pysam.pileup( "-c", "-f", "ex1.fa", "ex1.bam" ) if x.reference_base != "*"]
#         except pysam.SamtoolsError:
#             pass

#         i = samfile.pileup( stepper = "samtools", fastafile = fastafile )
#         calls = list(pysam.IteratorSNPCalls(i))
#         for x,y in zip( refs, calls ):
#             self.checkEqual( x, y )

#     def testPerPositionViaIterator( self ):
#         # test pileup for each position. This is a slow operation
#         # so this test is disabled 
#         return
#         samfile = pysam.Samfile( "ex1.bam", "rb")  
#         fastafile = pysam.Fastafile( "ex1.fa" )
#         for x in pysam.pileup( "-c", "-f", "ex1.fa", "ex1.bam" ):
#             if x.reference_base == "*": continue
#             i = samfile.pileup( x.chromosome, x.pos, x.pos+1,
#                                 fastafile = fastafile,
#                                 stepper = "samtools" )
#             z = [ zz for zz in pysam.IteratorSamtools(i) if zz.pos == x.pos ]
#             self.assertEqual( len(z), 1 )
#             self.checkEqual( x, z[0] )

#     def testPerPositionViaCaller( self ):
#         # test pileup for each position. This is a fast operation
#         samfile = pysam.Samfile( "ex1.bam", "rb")  
#         fastafile = pysam.Fastafile( "ex1.fa" )
#         i = samfile.pileup( stepper = "samtools", fastafile = fastafile )
#         caller = pysam.SNPCaller( i )

#         for x in pysam.pileup( "-c", "-f", "ex1.fa", "ex1.bam" ):
#             if x.reference_base == "*": continue
#             call = caller.call( x.chromosome, x.pos )
#             self.checkEqual( x, call )

# class TestIndelCalls( unittest.TestCase ):
#     '''test pysam indel calling.'''

#     def checkEqual( self, a, b ):

#         for x in ("pos",
#                   "genotype",
#                   "consensus_quality",
#                   "snp_quality",
#                   "mapping_quality",
#                   "coverage",
#                   "first_allele",
#                   "second_allele",
#                   "reads_first",
#                   "reads_second",
#                   "reads_diff"):
#             if b.genotype == "*/*" and x == "second_allele":
#                 # ignore test for second allele (positions chr2:439 and chr2:1512)
#                 continue
#             self.assertEqual( getattr(a, x), getattr(b,x), "%s mismatch: %s != %s\n%s\n%s" % 
#                               (x, getattr(a, x), getattr(b,x), str(a), str(b)))

#     def testAllPositionsViaIterator( self ):

#         samfile = pysam.Samfile( "ex1.bam", "rb")  
#         fastafile = pysam.Fastafile( "ex1.fa" )
#         try: 
#             refs = [ x for x in pysam.pileup( "-c", "-f", "ex1.fa", "ex1.bam" ) if x.reference_base == "*"]
#         except pysam.SamtoolsError:
#             pass

#         i = samfile.pileup( stepper = "samtools", fastafile = fastafile )
#         calls = [ x for x in list(pysam.IteratorIndelCalls(i)) if x != None ]
#         for x,y in zip( refs, calls ):
#             self.checkEqual( x, y )

#     def testPerPositionViaCaller( self ):
#         # test pileup for each position. This is a fast operation
#         samfile = pysam.Samfile( "ex1.bam", "rb")  
#         fastafile = pysam.Fastafile( "ex1.fa" )
#         i = samfile.pileup( stepper = "samtools", fastafile = fastafile )
#         caller = pysam.IndelCaller( i )

#         for x in pysam.pileup( "-c", "-f", "ex1.fa", "ex1.bam" ):
#             if x.reference_base != "*": continue
#             call = caller.call( x.chromosome, x.pos )
#             self.checkEqual( x, call )

class TestLogging( unittest.TestCase ):
    '''test around bug issue 42,

    failed in versions < 0.4
    '''

    def check( self, bamfile, log ):

        if log:
            logger = logging.getLogger('franklin')
            logger.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
            log_hand  = logging.FileHandler('log.txt')
            log_hand.setFormatter(formatter)
            logger.addHandler(log_hand)

        bam  = pysam.Samfile(bamfile, 'rb')
        cols = bam.pileup()
        self.assertTrue( True )

    def testFail1(self):
        self.check(os.path.join(DATADIR,"ex9_fail.bam"),
                   False)
        self.check(os.path.join(DATADIR,"ex9_fail.bam"),
                   True)

    def testNoFail1(self):
        self.check(os.path.join(DATADIR, "ex9_nofail.bam"),
                   False)
        self.check(os.path.join(DATADIR,"ex9_nofail.bam"),
                   True)

    def testNoFail2( self ):
        self.check(os.path.join(DATADIR,"ex9_nofail.bam"),
                   True)
        self.check(os.path.join(DATADIR,"ex9_nofail.bam"),
                   True)
        
# TODOS
# 1. finish testing all properties within pileup objects
# 2. check exceptions and bad input problems (missing files, optional fields that aren't present, etc...)
# 3. check: presence of sequence

class TestSamfileUtilityFunctions( unittest.TestCase ):

    def testCount( self ):

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                "rb")

        for contig in ("chr1", "chr2" ):
            for start in range( 0, 2000, 100 ):
                end = start + 1
                self.assertEqual(len( list( samfile.fetch( contig, start, end ) ) ),
                                 samfile.count( contig, start, end ) )

                # test empty intervals
                self.assertEqual(len( list( samfile.fetch( contig, start, start ) ) ),
                                 samfile.count( contig, start, start ) )

                # test half empty intervals
                self.assertEqual(len( list( samfile.fetch( contig, start ) ) ),
                                 samfile.count(contig, start))

    def testMate( self ):
        '''test mate access.'''

        with open(os.path.join(DATADIR,"ex1.sam"), "rb") as inf:
            readnames = [ x.split(b"\t")[0] for x in inf.readlines() ]
        if sys.version_info[0] >= 3:
            readnames = [ name.decode('ascii') for name in readnames ]
            
        counts = collections.defaultdict( int )
        for x in readnames: counts[x] += 1

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                "rb" )
        for read in samfile.fetch():
            if not read.is_paired:
                self.assertRaises( ValueError, samfile.mate, read )
            elif read.mate_is_unmapped:
                self.assertRaises( ValueError, samfile.mate, read )
            else:
                if counts[read.qname] == 1:
                    self.assertRaises( ValueError, samfile.mate, read )
                else:
                    mate = samfile.mate( read )
                    self.assertEqual( read.qname, mate.qname )
                    self.assertEqual( read.is_read1, mate.is_read2 )
                    self.assertEqual( read.is_read2, mate.is_read1 )
                    self.assertEqual( read.pos, mate.mpos )
                    self.assertEqual( read.mpos, mate.pos )

    def testIndexStats( self ):
        '''test if total number of mapped/unmapped reads is correct.'''

        samfile = pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                "rb")
        self.assertEqual( samfile.mapped, 3235 )
        self.assertEqual( samfile.unmapped, 35 )

class TestSamtoolsProxy( unittest.TestCase ):
    '''tests for sanity checking access to samtools functions.'''

    def testIndex( self ):
        self.assertRaises( IOError, pysam.index, "missing_file" )

    def testView( self ):
        # note that view still echos "open: No such file or directory"
        self.assertRaises( pysam.SamtoolsError, pysam.view, "missing_file" )

    def testSort( self ):
        self.assertRaises( pysam.SamtoolsError, pysam.sort, "missing_file" )

class TestSamfileIndex( unittest.TestCase):
    
    def testIndex( self ):
        samfile = pysam.Samfile(os.path.join(DATADIR,"ex1.bam"),
                                "rb")
        index = pysam.IndexedReads( samfile )
        index.build()

        reads = collections.defaultdict( int )

        for read in samfile: reads[read.qname] += 1
            
        for qname, counts in reads.items():
            found = list(index.find( qname ))
            self.assertEqual( len(found), counts )
            for x in found: self.assertEqual( x.qname, qname )
            

if __name__ == "__main__":
    # build data files
    print ("building data files")
    subprocess.call( "make -C %s" % DATADIR, shell=True)
    print ("starting tests")
    unittest.main()
    print ("completed tests")
