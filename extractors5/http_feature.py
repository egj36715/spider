# encoding=UTF-8
import codecs
import re
import json
import lxml
import numpy as np
import os
import sys
from lxml import html
from sklearn.externals import joblib
from sklearn_extensions.extreme_learning_machines import ELMClassifier

from extractor import Extractor

class HttpExtractor(Extractor):
    frame = None
    redirect = None
    submit = None
    empty = False

    def __init__(self, html_str, **kwargs):
        if 'url' in kwargs:
            self.url = str(kwargs['url']).rstrip()
            self.domain = self.get_domain_name(self.url)
        if 'tfidf_percent' in kwargs:
            if isinstance(kwargs['tfidf_percent'], float):
                self.tfidf_percent = kwargs['tfidf_percent']
            else:
                self.tfidf_percent = 0.9
        else:
            self.tfidf_percent = 0.9
        sys.stderr.write('TFIDF-percent: ' + str(self.tfidf_percent) + '\n')
        try:
            self.html_tree = html.fromstring(html_str)
                    
        except lxml.etree.ParserError:
            self.empty = True
            sys.stderr.write('no a no link\n')
        
        striped_html_str = self.__striped_html_str(html_str)
        self.total_rows = len(striped_html_str.split('\n'))
        self.bytes = self.get_bytes(striped_html_str)
        self.style_block_rows = self.get_style_block_rows(striped_html_str)
        self.script_block_rows = self.get_script_block_rows(striped_html_str)
        
        self.link_tags = self.get_link_tags()
        self.a_tags = self.get_a_tags()
        self.img_tags = self.get_img_tags()
        self.submit = self.get_submit()
        self.frame = self.get_iframe() + self.get_frame()
        self.redirect = self.get_redirect()
        self.script_tags = self.get_script_tags()
        self.title = self.get_title()
        
        self.bytes_distribution = self.__get_bytes_distribution(html_str)
        
        self.features = [self.get_kbytes, self.is_frame, self.is_meta_redirect, self.is_meta_base64_redirect, self.is_form, self.is_input_submit, self.is_button_submit, self.same_extern_domain_script_rate, self.script_block_rate, self.style_block_rate, self.external_a_tag_same_domain,self.null_a_tag,self.same_external_domain_link_rate, self.same_external_domain_img_rate, self.get_title_feature]
        
    def get_title(self):
        if self.empty:
            return []
        return self.html_tree.xpath('//title/text()')
        
    def get_title_feature(self):
        if not self.title:
            return 0
        with codecs.open('tfidf2 {:d}% term'.format(int(self.tfidf_percent * 100)), 'r', encoding='utf-8') as f:
            # nothing
            tf_position = json.loads(f.readline().rstrip())
            # get tf-idf terms
            tf_term = f.readline().rstrip().split(' ')
            sys.stderr.write('Load tfidf-{:d}%-elm.model\n'.format(int(self.tfidf_percent * 100)))
            # loading completed model
            elm = joblib.load('tfidf-{:d}%-elm.model'.format(int(self.tfidf_percent * 100)))
            
            if self.title:
                title_list = self.__split_title(self.title)
            else:
                return 0
            
            # initializing a empty features vector of elm model
            elm_vector = [[0] * len(tf_term)]
            # mapping data into the features vector of elm model
            for index, t in enumerate(tf_term):
                if t.lower() in title_list:
                    elm_vector[0][index] = 1
                    
            # classifing the title feature where in the elm model
            score = elm.predict(np.array(elm_vector))
            # must convert to list, because the output of elm.predict is numpy.array
            # which cannot using to train other model directly
            score = score.tolist()
            if isinstance(score, list):
                return score[0]
            else:
                return score
        
    def __split_title(self, title):
        delimiter = ['/', '?', '.', '=', '-', '_', '!',':', ';', '|', '(', ')', ',', '@', '"', "'", '[', ']',u'，', u'、', u'！', u'【', u'】', u'“', u'”', u'・', u'『', u'』', u'｜', u'‹', u'›', u'丨', u'¥']
        tf_test = []
        for t in title:
            t = t.strip()
            for d in delimiter:
                t = t.replace(d, ' ')
            tf_test += [i.lower() for i in t.split(' ') if i]
        return tf_test
        
    def __get_bytes_distribution(self, html_str):
        temp = [0]*256
        for line in html_str.split('\n'):
            for c in line:
                temp[ord(c)] += 1
        return temp
        
    def get_bytes_distribution(self):
        if not self.empty:
            return self.bytes_distribution
        return []
        
    def get_bytes(self, html_str):
        return len(html_str)
    
    def get_kbytes(self):
        return float(self.bytes)/1024.0
        
    def __striped_html_str(self, html_str):
        temp = html_str.rstrip()
        striped_html_str = []
        for row in temp.split('\n'):
            if re.match('^<!--.*(-->.*<!--)+.*-->$', row.rstrip()):
                striped_html_str.append(row.rstrip())
            elif re.match('^<!--.*-->$', row.rstrip()):
                continue
            else:
                striped_html_str.append(row.rstrip())
        return '\n'.join(striped_html_str)

    def __cal_tag_block_rows(self, html_str, tag_name):
        temp = 0
        if not self.empty:
            block_begin = -1
            for i, row in enumerate(html_str.split('\n')):
                if row.find(tag_name) > 0:
                    l = len(re.findall('<'+tag_name, row.rstrip()))
                    r = len(re.findall('</'+ tag_name +'>', row.rstrip()))
                    if l > r:
                        block_begin = i
                    elif r > l and block_begin > 0:
                        temp += i - block_begin + 1
                        block_begin = -1
                    elif l > 0:
                        temp += 1
        return temp
        

    def get_script_block_rows(self, html_str):
        return self.__cal_tag_block_rows(html_str, 'script')
        
    def script_block_rate(self):
        if self.total_rows > 0:
            return float(self.script_block_rows)/float(self.total_rows)
        return 0.0
        
    def get_style_block_rows(self, html_str):
        return self.__cal_tag_block_rows(html_str, 'style')

    def style_block_rate(self):
        if self.total_rows > 0:
            return float(self.style_block_rows)/float(self.total_rows)
        return 0.0

    def set_url(self, url):
        self.url = url
        sys.stderr.write(self.url)
        return self

    def get_url(self):
        return self.url

    def get_iframe(self):
        if not self.empty:
            return self.html_tree.xpath('//iframe')
        return []

    def get_frame(self):
        if not self.empty:
            return self.html_tree.xpath('//frame')
        return []

    def frame_feature(self):
        frame = self.get_frame()
        if frame:
            return len(frame)
        else:
            return 0
            
    #7
    def is_frame(self):
        if self.frame:
            return True
        return False

    def get_redirect(self):
        if not self.empty:
            redirect = []
            for i in self.html_tree.xpath('//meta'):
              if i.get('http-equiv') is not None:
                if re.match('^refresh$', i.get('http-equiv'), re.IGNORECASE):
                    redirect.append(i)
            # return self.html_tree.xpath('//meta[@http-equiv="refresh"]') + self.html_tree.xpath('//meta[@http-equiv="Refresh"]') + self.html_tree.xpath('//meta[@http-equiv="REFRESH"]')
            return redirect
        return []
    
    def is_meta_base64_redirect(self):
        for i in self.redirect:
            if re.match('^.*base64.*$', i.get('content').lower(), re.IGNORECASE):
                return True
        return False
        
    def is_meta_redirect(self):
        if self.is_redirect() and not self.is_meta_base64_redirect():
            return True
        return False
    
    def redirect_feature(self):
        redirect = self.get_redirect()
        if redirect:
            return len(redirect)
        else:
            return 0

    #8
    def is_redirect(self):
        if self.redirect:
            return True
        return False

    def submit_feature(self):
        sumit = self.get_submit()
        if submit:
            return len(submit)
        else:
            return 0

    def get_submit(self):
        if not self.empty:
            return self.html_tree.xpath('//*[@type="submit"]')
        return []
    
    def is_input_submit(self):
        for i in self.submit:
          if i.tag == 'input':
            return True
        return False

    def is_button_submit(self):
        for i in self.submit:
          if i.tag == 'button':
            return True
        return False
            
    #9
    def is_submit(self):
        if self.submit:
            return True
        return False
    
    def get_a_tags(self):
        if not self.empty:
            return self.html_tree.xpath('//a')
        return []
    
    def external_a_tag_same_domain(self):
        if self.empty:
            return 0.0
        urls = {}
        total = 0
        null_url = 0
        for node in self.a_tags:
            url = node.get('href')
            total += 1
            if url and url != '#' and url != '':
                domain_name = self.get_domain_name(url)
                if domain_name in urls:
                    urls[domain_name] += 1
                else:
                    urls[domain_name] = 1
            else:
                null_url += 1
        m = 0
        for domain_name in urls:
            if urls[domain_name] > m and domain_name != '.' and domain_name != self.domain:
                m = urls[domain_name]
        if total > 0:
            return float(m)/float(total)
        return 0
    
    def null_a_tag(self):
        if self.empty:
            return 0.0
        urls = {}
        total = 0
        null_url = 0
        for node in self.a_tags:
            url = node.get('href')
            total += 1
            if url and not url.startswith('#') and url != '' and 'void(' not in url:
                domain_name = self.get_domain_name(url)
                if domain_name in urls:
                    urls[domain_name] += 1
                else:
                    urls[domain_name] = 1
            else:
                null_url += 1
        m = null_url
        if total > 0:
            return float(m)/float(total)
        return 0
    
    def get_link_tags(self):
        if not self.empty:
            return self.html_tree.xpath('//link')
        return []
    
    def same_external_domain_link_rate(self):
        if self.empty:
            return 0.0
        urls = {}
        total = 0
        null_url = 0
        for node in self.link_tags:
            url = node.get('href')
            total += 1
            if url and url != '#' and url != '':
                domain_name = self.get_domain_name(url)
                if domain_name in urls:
                    urls[domain_name] += 1
                else:
                    urls[domain_name] = 1
            else:
                null_url += 1
        
        m = 0
        for domain_name in urls:
            if urls[domain_name] > m and domain_name != '.' and domain_name != self.domain:
                m = urls[domain_name]
        if total > 0:
            return float(m)/float(total)
        return 0
    
    def get_img_tags(self):
        if not self.empty:
            return self.html_tree.xpath('//img')
        return []
    
    def same_external_domain_img_rate(self):
        if self.empty:
            return 0.0
        urls = {}
        total = 0
        null_url = 0
        for node in self.img_tags:
            url = node.get('src')
            total += 1
            if url:
                domain_name = self.get_domain_name(url)
                if domain_name in urls:
                    urls[domain_name] += 1
                else:
                    urls[domain_name] = 1
            else:
                null_url += 1
        m = 0
        for domain_name in urls:
            if urls[domain_name] > m and domain_name != '.' and domain_name != self.domain:
                m = urls[domain_name]
        if total > 0:
            return float(m)/float(total)
        else:
            return 0
    
    def get_form(self):
        if not self.empty:
            return self.html_tree.xpath('//form')
        return None
    
    def is_form(self):
       if self.get_form():
           return True
       return False
    
    def get_script_tags(self):
        if not self.empty:
            return self.html_tree.xpath('//script')
        return []

    def same_extern_domain_script_rate(self):
        if self.empty:
            return 0.0
        temp = {}
        total = 0
        null_url = 0
        for tag in self.script_tags:
            url = tag.get('src')
            total += 1
            if url:
                domain_name = self.get_domain_name(url)
                if domain_name not in temp:
                    temp[domain_name] = 1
                else:
                    temp[domain_name] +=1
            else:
                null_url += 1
        m = 0
        for domain in temp:
            if domain != '.' and temp[domain] > m and domain != self.domain:
                m = temp[domain]
                
        if total > 0:
            return float(m)/float(total)
        return 0.0
        
    def title_features(self):
        title_list = self.html_tree.xpath('//title/text()')
        with codecs.open('tfidf-term', 'r', encoding='utf-8') as f:
            f.readline()
            tfidf_set = f.readline().rstrip().split(' ')
        temp = [0] * len(tfidf_set)
        if not title_list:
            return temp
        else:
            delimiter = ['/', '?', '.', '=', '-', '_', '!',':', ';', '|', '(', ')', ',', '@', '"', "'", '[', ']',u'，', u'、', u'！', u'【', u'】', u'“', u'”', u'・', u'『', u'』', u'｜', u'‹', u'›', u'丨', u'¥']
            for title in title_list:
                for d in delimiter:
                    title = title.replace(d, ' ')
                for t in title.split().split(' '):
                    if t in tfidf_set:
                        temp[tfidf_set.index(t)] += 1
            return temp
        
    def __add__(self, other):
        self.a_tags += other.a_tags
        self.link_tags += other.link_tags
        self.img_tags += other.img_tags
        self.submit += other.submit
        self.frame += other.frame
        self.redirect += other.redirect
        self.style_block_rows += other.style_block_rows
        self.script_block_rows += other.script_block_rows
        self.total_rows += other.total_rows
        self.script_tags += other.script_tags
        self.bytes += other.bytes
        self.title += other.title
        
        for i in range(256):
            self.bytes_distribution[i] += other.bytes_distribution[i]
        
        return self
